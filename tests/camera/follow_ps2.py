#!/usr/bin/env python3
"""№407/408: default comparison uses 25 actual tPointCamera snapshots on V104 trajectories.

Run with python3.14. Typed original Wheel byte-A callbacks drive the replay;
raw word257 is not treated as Boolean1. Sparse original eyes are never filled
with listener positions or interpolation. Missing speed-v28 and dense air
pitch variance remain explicit partial coverage; land remains diagnostic.
The historical listener diagnostic below requires --legacy-listener, returns
rc2 and cannot accept actual-camera behavior.

Historical listener diagnostic (superseded):

Настоящий chaseCamUpdate из viewer/main.c (тот же способ сборки, что tests/camera/chase_motion.py) получает траекторию машины
оригинала из записей близнеца (50 Гц, строки через 2 кадра — подшаги 1/50 с, скорость — разность положений) и выдаёт глаз;
сверяется с глазом камеры PS2 в той же записи (блок камеры 0x7aaba0, knowledge/facts/ps2-camera-fov.yaml). Абсолютные дистанция и
высота у порта намеренно другие (правки 198+ и 360: угол кадра шире, ×1,10), поэтому сверка — по ОТКЛОНЕНИЯМ от своего
установившегося значения (ровная езда > 12 м/с): как глаз меняется со скоростью, на разгоне/торможении, на трамплине, в полёте и после
посадки.

Записи (оси диска: z как в записи; порт получает z со знаком минус и отдаёт обратно):
  v28  build/twins/o4/v28_drive_cam/drive.tsv                           3000 кадров езды по маршруту с поворотами и остановками
  jz2  build/twins/o4/codex378_jz2_0702/camera.tsv + jump.tsv           трамплин jumpzone2 (G14), ~88 км/ч, без камер зон
  house build/codex-terminal/rob-rest/378/attempt1/original-house-native2  разгон и подъезд к дому (до кадра 920: камера за машиной)

  python3 tests/camera/follow_ps2.py               сводка и гейт по текущему main.c
  python3 tests/camera/follow_ps2.py --source F    то же на другом main.c (красный контроль — прежний код)
  python3 tests/camera/follow_ps2.py -D CAM_PULL_OLD=1   то же с макросом сборки (красный контроль без отдельного файла)
Гейт (зелёный, если все пункты в допуске):
  speed   — дистанция на скорости минус на малой скорости (v28): |порт − PS2| ≤ 0,15 м
  air     — высота глаза над машиной в полёте jz2 (кадры 900–960) минус установившаяся: |порт − PS2| ≤ 0,5 м
  pitch   — наклон взгляда в полёте jz2 минус установившийся: |порт − PS2| ≤ 3°, разброс в полёте ≤ 1° (у PS2 взгляд замирает, В30)
  ramp    — то же на въезде на трамплин jz2 (кадры 884–896): |порт − PS2| ≤ 0,6 м
ОТКРЫТО (печатается, в гейт не входит): land — то же через 0,5–1,5 с после посадки jz2 (кадры 994–1040). У PS2 наклон после
посадки спадает к 0 за ~1,5 с и НЕ идёт за тангажом кузова (−15° на отскоке) и за уклоном ямы (−10°); что его ведёт — не измерено
(вопрос близнецу В104). Модель порта (пол кузова на земле) на тангаже кузова PS2 даёт здесь +0,6 м к PS2.
Красные контроли: -D CAM_PULL_OLD=1 (speed), -D CAM_TILT_OLD=1 (ramp, air)."""
import argparse, math, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/camera'))
from chase_motion import function  # noqa: E402

REC = {
    'v28': (ROOT / 'build/twins/o4/v28_drive_cam/drive.tsv', None),
    'jz2': (ROOT / 'build/twins/o4/codex378_jz2_0702/camera.tsv', ROOT / 'build/twins/o4/codex378_jz2_0702/jump.tsv'),
    'house': (ROOT / 'build/codex-terminal/rob-rest/378/attempt1/original-house-native2/camera.tsv',
              ROOT / 'build/codex-terminal/rob-rest/378/attempt1/original-house-native2/jump.tsv'),
}

HARNESS = r'''
int main(void) {
  Car c; memset(&c, 0, sizeof c); strncpy(c.p.name, "famil_v", sizeof c.p.name - 1);
  c.p.bodyHi = 1.65f; c.p.halfL = 2.675f; c.p.bodyOfs = -.32f; c.p.camElev = 1.23f; c.p.camMag = 7.2f; c.q[0] = 1.f;
  float dt, x, y, z, h, vx, vy, vz, sl, cam[3], look[3]; int wh;
  memset(&chase, 0, sizeof chase);
  while (scanf("%f %f %f %f %f %f %f %f %d %f", &dt, &x, &y, &z, &h, &vx, &vy, &vz, &wh, &sl) == 10) {
    c.x = x; c.y = y; c.z = z; c.h = h; c.vel[0] = vx; c.vel[1] = vy; c.vel[2] = vz;
    c.wheels = wh; c.grounded = wh > 0; c.gx = sl * sinf(h); c.gz = sl * cosf(h);   // пол кузова: уклон по курсу
    chaseCamUpdate(&c, 0.f, dt, cam, look);
    printf("%.5f %.5f %.5f %.5f %.5f %.5f\n", cam[0], cam[1], cam[2], look[0], look[1], look[2]);
  }
  return 0;
}
'''


def build(source, defines, out):
    src = Path(source).read_text()
    defs = '\n'.join(re.findall(r'^#define CAM_[A-Z0-9_]+\s+[^\n]+', src, re.M))
    state = re.search(r'typedef struct \{ int init;.*?\} ChaseCam;', src).group()
    info = re.search(r'typedef struct \{ const char \*name; int ps2;.*?\} ChaseInfo;', src).group()
    pre = r'''
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "car.h"
#include "carcam.h"
#define GU_PI 3.14159265f
#define FOVY 62.f
#define ASPECT (480.f/272.f)
#define NEAR_Z .7f
static int gameLevel=1, haveCol, chaseOld, chaseLevelOld, camHighOld, camGroundOld, chaseWallOff;
static ColWorld world;
static float chaseNear;
static struct {float lift;} cv;
static int ground(float x,float z,float top,float bottom,float *g) { (void)x;(void)z;(void)top;(void)bottom;(void)g; return 0; }
static float camCarsFrac(const float *t,const float *e) {(void)t;(void)e;return 1.f;}
'''
    code = pre + defs + '\n' + state + '\nstatic ChaseCam chase;\n' + info + '\nstatic ChaseInfo chaseInfo;\n'
    code += '\n'.join(function(src, f) for f in ('cdStep', 'wrapPi', 'carCamFind', 'camFit', 'chaseCamUpdate')) + HARNESS
    out.parent.mkdir(parents=True, exist_ok=True)
    cf = out.with_suffix('.c'); cf.write_text(code)
    cmd = ['cc', '-std=c11', '-O2', '-w', '-DSKIN_HOST', *[f'-D{d}' for d in defines], '-I', str(ROOT / 'viewer'), str(cf),
           str(ROOT / 'viewer/car.c'), str(ROOT / 'viewer/col.c'), '-lm', '-o', str(out)]
    subprocess.run(cmd, check=True)


def load(name):
    """-> [dict(f, p (оси записи), fw (курс записи, x z), eye (оси записи), v, phase)]"""
    path, jpath = REC[name]
    lines = path.read_text().splitlines(); h = lines[0].split('\t'); rows = []
    J = {}
    if jpath:
        for l in jpath.read_text().splitlines()[1:]:
            r = l.split('\t'); J[int(float(r[0]))] = r
    for l in lines[1:]:
        r = l.split('\t')
        try: vals = [float(v) for v in r[:1]] + r[1:]
        except ValueError: continue
        f = int(float(r[0]))
        if name == 'v28':
            x, y, z, hd, v = (float(r[i]) for i in (1, 2, 3, 4, 5)); cx, cy, cz = (float(r[i]) for i in (9, 10, 11))
            fw = (math.sin(math.radians(hd)), math.cos(math.radians(hd))); ph = ''
        else:
            x, y, z, nx, nz = (float(r[i]) for i in (1, 2, 3, 4, 5)); cx, cy, cz = (float(r[i]) for i in (7, 8, 9))
            ln = math.hypot(nx, nz) or 1.; fw = (nx / ln, nz / ln)
            j = J.get(f); v = float(j[5]) if j and j[5] else 0.; ph = j[8] if j else ''
        pitch = float(j[10]) if name != 'v28' and j and j[10] else None
        rows.append(dict(f=f, p=(x, y, z), fw=fw, eye=(cx, cy, cz), v=v, ph=ph, pitch=pitch))
    # колёса на земле и уклон пола кузова по курсу (вход наклона камеры): у v28 — всё на земле, уклон — по траектории (±3 строки);
    # у прыжков — тангаж кузова из jump.tsv, полёт — от первой строки «полёт» до посадки (скачок vy вверх > 4 м/с за строку)
    land = None; start = next((r['f'] for r in rows if r['ph'] == 'полёт'), None)
    for i, r in enumerate(rows):
        a = rows[max(0, i - 3)]; b = rows[min(len(rows) - 1, i + 3)]; ds = math.hypot(b['p'][0] - a['p'][0], b['p'][2] - a['p'][2])
        r['slope'] = (b['p'][1] - a['p'][1]) / ds if ds > .5 else 0.
        if r['pitch'] is not None: r['slope'] = math.tan(math.radians(r['pitch']))
        r['air'] = False
        if start is not None and r['f'] >= start and land is None:
            if i and r['f'] > start and (r['p'][1] - rows[i - 1]['p'][1]) - (rows[i - 1]['p'][1] - rows[i - 2]['p'][1]) > .15: land = r['f']
            else: r['air'] = True
    return rows


def replay(exe, rows):
    """траектория оригинала -> глаз порта в осях записи на кадрах строк"""
    inp = []
    n = len(rows)
    for i, r in enumerate(rows):
        a = rows[max(0, i - 1)]; b = rows[min(n - 1, i + 1)]; span = (b['f'] - a['f']) / 50. or 1.
        vel = [(b['p'][k] - a['p'][k]) / span for k in range(3)]
        if i == 0: steps = [(1 / 50., r['p'])]
        else:
            q = rows[i - 1]; k = max(1, r['f'] - q['f'])
            steps = [(1 / 50., tuple(q['p'][m] + (r['p'][m] - q['p'][m]) * (s + 1) / k for m in range(3))) for s in range(k)]
        h = math.atan2(r['fw'][0], -r['fw'][1])          # курс движка (z отзеркален)
        for dt, p in steps:
            inp.append(f"{dt:.6f} {p[0]:.5f} {p[1]:.5f} {-p[2]:.5f} {h:.6f} {vel[0]:.5f} {vel[1]:.5f} {-vel[2]:.5f} "
                       f"{0 if r['air'] else 4} {r['slope']:.5f}")
    out = subprocess.run([str(exe)], input='\n'.join(inp) + '\n', capture_output=True, text=True, check=True).stdout.split('\n')
    eyes, k = [], 0
    for i, r in enumerate(rows):
        k += 1 if i == 0 else max(1, r['f'] - rows[i - 1]['f'])
        e = [float(v) for v in out[k - 1].split()[:6]]
        eyes.append((e[0], e[1], -e[2], e[3], e[4], -e[5]))
    return eyes


def rel(r, eye):
    """глаз относительно машины: (позади по курсу, по горизонтали; над машиной)"""
    dx, dz = eye[0] - r['p'][0], eye[2] - r['p'][2]
    return -(dx * r['fw'][0] + dz * r['fw'][1]), eye[1] - r['p'][1]


def mean(v): return sum(v) / len(v) if v else float('nan')


def metrics(exe):
    M = {}
    rows = load('v28'); eyes = replay(exe, rows)
    P = [rel(r, r['eye']) for r in rows]; Q = [rel(r, e) for r, e in zip(rows, eyes)]
    fast = [i for i, r in enumerate(rows) if r['v'] > 14 and r['f'] > 100]
    slow = [i for i, r in enumerate(rows) if r['v'] < 3 and r['f'] > 100]
    for tag, S in (('ps2', P), ('port', Q)):
        M[f'v28_{tag}_back_fast'] = mean([S[i][0] for i in fast]); M[f'v28_{tag}_back_slow'] = mean([S[i][0] for i in slow])
        M[f'v28_{tag}_h_fast'] = mean([S[i][1] for i in fast]); M[f'v28_{tag}_h_slow'] = mean([S[i][1] for i in slow])
    M['speed_ps2'] = M['v28_ps2_back_fast'] - M['v28_ps2_back_slow']; M['speed_port'] = M['v28_port_back_fast'] - M['v28_port_back_slow']
    M['n_fast'], M['n_slow'] = len(fast), len(slow)
    rows = load('jz2'); eyes = replay(exe, rows)
    # взгляд камеры (наклон вниз, °) в полёте относительно ровной езды и его разброс: у PS2 взгляд в полёте «замирает» (аудит 09.10, В30)
    J = {int(float(l.split('\t')[0])): l.split('\t') for l in REC['jz2'][0].read_text().splitlines()[1:]}
    PP = [math.degrees(math.asin(float(J[r['f']][11]))) for r in rows]
    PQ = [math.degrees(math.atan2(e[4] - e[1], math.hypot(e[3] - e[0], e[5] - e[2]))) for e in eyes]
    for tag, S in (('ps2', PP), ('port', PQ)):
        b = mean([S[i] for i, r in enumerate(rows) if 700 <= r['f'] <= 780]); A = [S[i] for i, r in enumerate(rows) if 900 <= r['f'] <= 960]
        M[f'pitch_{tag}'] = mean(A) - b; M[f'pitchsd_{tag}'] = (sum((x - mean(A)) ** 2 for x in A) / len(A)) ** .5
    P = [rel(r, r['eye']) for r in rows]; Q = [rel(r, e) for r, e in zip(rows, eyes)]
    base = [i for i, r in enumerate(rows) if 700 <= r['f'] <= 780]
    for tag, S in (('ps2', P), ('port', Q)):
        b = mean([S[i][1] for i in base])
        for seg, lo, hi in (('ramp', 884, 896), ('air', 900, 960), ('land', 994, 1040)):
            M[f'{seg}_{tag}'] = mean([S[i][1] for i, r in enumerate(rows) if lo <= r['f'] <= hi]) - b
        M[f'jz2_{tag}_series'] = [(r['f'], round(S[i][0], 2), round(S[i][1], 2)) for i, r in enumerate(rows) if 860 <= r['f'] <= 1080 and r['f'] % 8 == 0]
    return M


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=str(ROOT / 'viewer/main.c')); ap.add_argument('-D', action='append', default=[])
    ap.add_argument('--out', default=str(ROOT / 'build/camera/follow_ps2/host')); ap.add_argument('--series', action='store_true')
    ap.add_argument('--evidence-root')
    ap.add_argument('--legacy-listener', action='store_true', help='Historical diagnostic only; no actual camera acceptance')
    a = ap.parse_args()
    if not a.legacy_listener:
        from native_follow import run
        try:
            return run(a)
        except (ValueError,OSError) as e:
            print(str(e),file=sys.stderr)
            return 2
    print('INVALID CAMERA REFERENCE: legacy 0x7aaba0 is radSoundHalListener; diagnostic only')
    exe = Path(a.out + ('_' + '_'.join(re.sub(r'\W', '', d) for d in a.D) if a.D else '')); build(a.source, a.D, exe)
    M = metrics(exe)
    print(f"v28: позади на скорости/на малой — PS2 {M['v28_ps2_back_fast']:.2f}/{M['v28_ps2_back_slow']:.2f} м, порт "
          f"{M['v28_port_back_fast']:.2f}/{M['v28_port_back_slow']:.2f} м (кадров {M['n_fast']}/{M['n_slow']})")
    print(f"v28: высота на скорости/на малой — PS2 {M['v28_ps2_h_fast']:.2f}/{M['v28_ps2_h_slow']:.2f}, порт {M['v28_port_h_fast']:.2f}/{M['v28_port_h_slow']:.2f}")
    if a.series:
        for p, q in zip(M['jz2_ps2_series'], M['jz2_port_series']): print('jz2', p, q)
    ok = True
    for key, tol, what in (('speed', .15, 'прибавка дистанции со скоростью'), ('ramp', .6, 'высота глаза на въезде на трамплин'),
                           ('air', .5, 'высота глаза в полёте'), ('land', None, 'высота глаза после посадки')):
        d = M[f'{key}_port'] - M[f'{key}_ps2']; good = tol is None or abs(d) <= tol; ok &= good
        tag = 'ОТКРЫТО' if tol is None else ('PASS' if good else 'FAIL')
        print(f"{tag} {key}: {what} — PS2 {M[f'{key}_ps2']:+.2f} м, порт {M[f'{key}_port']:+.2f} м (разница {d:+.2f}"
              + (f", допуск ±{tol})" if tol is not None else ", вне гейта: В104)"))
    d = M['pitch_port'] - M['pitch_ps2']; good = abs(d) <= 3. and M['pitchsd_port'] <= 1.; ok &= good
    print(f"{'PASS' if good else 'FAIL'} pitch: взгляд в полёте jz2 (кадры 900–960) относительно ровной езды — PS2 {M['pitch_ps2']:+.1f}° "
          f"(разброс {M['pitchsd_ps2']:.2f}°), порт {M['pitch_port']:+.1f}° (разброс {M['pitchsd_port']:.2f}°); допуск ±3°, разброс ≤ 1°")
    print('PASS follow camera vs PS2' if ok else 'FAIL follow camera vs PS2')
    return 2  # Historical listener comparison cannot accept actual camera behavior.


if __name__ == '__main__':
    raise SystemExit(main())
