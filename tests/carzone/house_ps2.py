#!/usr/bin/env python3
"""№378/№408 (пункт ДОБИВКИ 17): камеры зон машины у дома с трамплином L1 и на трамплинах jz2/jz16 против записей PS2.

Настоящий carZoneStep (viewer/carzone.c + roomcam.c) с пакетом камер уровня 1 прямо с диска (tools/zonecam_export.py --car)
получает траекторию машины ОРИГИНАЛА из записей наблюдателя (каждые 2 кадра PAL; матрица кузова — положение и оси, скорость):
кузов — коробка famil_v (полуширина 1,10, полудлина 2,675, сдвиг −0,32, днище 0,28 и крыша 1,65 над землёй, земля 0,70 под
началом модели — как tests/camera/carzone_ps2.py), body[0] — её середина. Сверка:

  A. тип активной камеры PS2 (прочитан из SuperCamCentral: FollowCam / RailCam / StaticCam; факт ps2-house-native-supercam.yaml):
     В95 50 км/ч  Follow → Static 266;  В95 70  Follow → Rail 166 → Follow 196 → Static 198;  В95 полный газ  Follow → Rail 148 →
     Follow 216;  В81 (машина на крыше, назад/руль)  Static все 800 кадров. Зелёный: порядок камер тот же (схлопнутая
     последовательность совпадает), каждая смена PS2 — сменой порта на ту же камеру в ±4 кадра, вне ±4 кадров у смен тип в каждой
     строке совпадает;
  B. В103 70/80/90/накат 100 (факт ps2-house-camera-speeds.yaml): первая камера зоны порта — r1_cam1 в ±4 кадра от первого резкого
     смещения глаза PS2 (166/156/150/150); каждый срез глаза PS2 (шаг > 3 м за строку) — смена камеры порта в ±4 кадра;
  C. глаз: пока порт снимает камерой зоны (вне ±4 кадров у смен), угол «машина → глаз порта» к «машина → глаз PS2» в среднем
     ≤ 6° у рельса и ≤ 1° у статичной, разница дистанций ≤ 0,6 / 0,2 м (допуски tests/camera/carzone_ps2.py);
  D. В104 jz2 70/100/длинный 100, jz16 70/100 (факт ps2-camera-after-landing.yaml) и codex378_jz2_0702 (88 км/ч): камер зон
     у PS2 нет — порт ни в одной строке не снимает камерой зоны («на jz2 сбоку не снимать»).

Записи (только чтение): $SHAR_PS2W (по умолчанию ~/Downloads/shar-psp-ps2-w)/build/twins/o4/<запись>/trace.tsv — sha256 сверяется
с фактом, где он там записан; codex378_jz2_0702 — build/twins/o4 этого дерева или ~/Downloads/shar-psp/build/twins/o4.

  python3 tests/carzone/house_ps2.py                           зелёный
  python3 tests/carzone/house_ps2.py -D CARZONE_PS2_OLD=1      красный: прежнее (порог 20 м/с, рельс держит касание кузова,
                                                               текущая камера не уступает новой)
  python3 tests/carzone/house_ps2.py -D CARZONE_RAIL_MINV=20   красный: прежний порог (на 70 км/ч рельс не включается)
  python3 tests/carzone/house_ps2.py -D CARZONE_RAIL_MINV=0    красный: рельс на любой скорости (В95 50 включает r1_cam1)"""
import argparse, hashlib, json, math, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS2W = Path(os.environ.get('SHAR_PS2W', Path.home() / 'Downloads/shar-psp-ps2-w'))
O4 = PS2W / 'build/twins/o4'
FACTS = PS2W / 'knowledge/facts'
HALF_W, HALF_L, OFS, LO, HI, ORIGIN = 1.10, 2.675, -0.32, 0.28, 1.65, 0.70
PTR = {0x166d680: 'F', 0x17fe8d0: 'R', 0x17fdfb0: 'S'}   # активная SuperCam (факт ps2-house-native-supercam.yaml, native_binding)
NAME = {'-': 'F', 'r1_cam1': 'R', 'z1_housejump': 'S'}
NEAR = 4   # кадров: допуск смены камеры (как tests/camera/carzone_ps2.py)

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "carzone.h"
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  RoomCam cams[CARZONE_CAMS]; int nc = roomCamsParse(cams, CARZONE_CAMS, b, (unsigned)n);
  if (nc <= 0) { printf("BADPACK %d\n", nc); return 2; }
  CarZoneState s; memset(&s, 0, sizeof s); s.cur = -1;
  float dt, ref[3], sp, body[9][3], eye[3], look[3], fy;
  while (scanf("%f %f %f %f %f", &dt, &ref[0], &ref[1], &ref[2], &sp) == 5) {
    for (int i = 0; i < 9; i++) if (scanf("%f %f %f", &body[i][0], &body[i][1], &body[i][2]) != 3) return 3;
    int k = carZoneStep(cams, nc, &s, (const float (*)[3])body, 9, ref, sp, dt, eye, look, &fy);
    if (k >= 0) printf("%s %.4f %.4f %.4f\n", cams[k].name, eye[0], eye[1], eye[2]);
    else printf("- 0 0 0\n");
  }
  return 0;
}
'''


def build(defines, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    c = out.with_suffix('.c'); c.write_text(HARNESS)
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', *[f'-D{d}' for d in defines], '-I', str(ROOT / 'viewer'), str(c),
                    str(ROOT / 'viewer/carzone.c'), str(ROOT / 'viewer/roomcam.c'), '-lm', '-o', str(out)], check=True)


def pack(out):
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'tools/zonecam_export.py'), '--level', '1', '--car', '--out', str(out)],
                   check=True, capture_output=True)


def fact(name):
    return json.loads((FACTS / f'{name}.yaml').read_text())


def sha_of(run):
    """sha256 трассы из факта (если записан)"""
    for f in ('ps2-house-native-supercam',):
        for r in fact(f)['evidence']['runs']:
            if isinstance(r, dict) and r['run'].endswith('/' + run): return r.get('trace_sha256')
    return None


def box(T, R, U, F):
    """середина и 8 углов коробки кузова (оси записи) -> оси движка (z отзеркален)"""
    def P(x, y, z): return tuple(T[i] + R[i] * x + U[i] * y + F[i] * z for i in range(3))
    pts = [P(0, (LO + HI) / 2 - ORIGIN, OFS)]
    for a in (-HALF_L, HALF_L):
        for b in (-HALF_W, HALF_W):
            for h in (LO, HI): pts.append(P(b, h - ORIGIN, OFS + a))
    return [(x, y, -z) for x, y, z in pts]


def load_trace(run):
    p = O4 / run / 'trace.tsv'
    data = p.read_bytes(); want = sha_of(run)
    if want and hashlib.sha256(data).hexdigest() != want: raise SystemExit(f'FAIL {run}: trace.tsv не совпал с sha256 факта')
    L = data.decode().splitlines(); H = L[0].split('\t'); rows = []
    for l in L[1:]:
        d = dict(zip(H, l.split('\t'))); m = [float(d[f'mat[{k}]']) for k in range(16)]
        v = [float(d[f'car_vel[{k}]']) for k in range(3)]
        rows.append(dict(f=int(d['rel']), T=tuple(m[12:15]), body=box(m[12:15], m[0:3], m[4:7], m[8:11]), sp=math.hypot(v[0], v[2]),
                         eye=tuple(float(d[f'cam_pos[{k}]']) for k in range(3)),
                         ps2=PTR.get(int(float(d['active_supercam_ptr']))) if 'active_supercam_ptr' in d else None))
    return rows


def load_codex378():
    for base in (ROOT / 'build/twins/o4', Path.home() / 'Downloads/shar-psp/build/twins/o4'):
        d = base / 'codex378_jz2_0702'
        if (d / 'camera.tsv').exists(): break
    J = {int(float(l.split('\t')[0])): l.split('\t') for l in (d / 'jump.tsv').read_text().splitlines()[1:]}
    rows = []; L = (d / 'camera.tsv').read_text().splitlines()[1:]
    for i, l in enumerate(L):
        r = [float(x) for x in l.split('\t')]; f = int(r[0]); j = J.get(f)
        pitch = math.radians(float(j[10])) if j and j[10] else 0.
        fx, fz = r[4], r[5]; n = math.hypot(fx, fz) or 1.; fx /= n; fz /= n
        F = (fx * math.cos(pitch), math.sin(pitch), fz * math.cos(pitch)); U = (-fx * math.sin(pitch), math.cos(pitch), -fz * math.sin(pitch))
        R = (U[1] * F[2] - U[2] * F[1], U[2] * F[0] - U[0] * F[2], U[0] * F[1] - U[1] * F[0])
        rows.append(dict(f=f, T=(r[1], r[2], r[3]), body=box((r[1], r[2], r[3]), R, U, F), eye=(r[7], r[8], r[9]), ps2=None, sp=0.))
    for i, r in enumerate(rows):
        a = rows[max(0, i - 1)]; b = rows[min(len(rows) - 1, i + 1)]; span = (b['f'] - a['f']) / 50. or 1.
        r['sp'] = math.hypot(b['T'][0] - a['T'][0], b['T'][2] - a['T'][2]) / span
    return rows


def replay(exe, packf, rows):
    lines = []
    for i, r in enumerate(rows):
        dt = (r['f'] - rows[i - 1]['f']) / 50. if i else 1 / 50.
        T = r['T']
        lines.append(f"{dt:.5f} {T[0]:.4f} {T[1]:.4f} {-T[2]:.4f} {r['sp']:.4f} " + ' '.join(f'{x:.4f} {y:.4f} {z:.4f}' for x, y, z in r['body']))
    out = subprocess.run([str(exe), str(packf)], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout.splitlines()
    for r, o in zip(rows, out):
        t = o.split(); r['cam'] = t[0]; r['port'] = NAME.get(t[0], t[0]); r['peye'] = (float(t[1]), float(t[2]), -float(t[3]))
    return rows


def seq(rows, key):
    s = []
    for r in rows:
        if not s or s[-1][0] != r[key]: s.append([r[key], r['f'], r['f']])
        else: s[-1][2] = r['f']
    return s


def ang(u, v):
    c = sum(a * b for a, b in zip(u, v)) / (math.sqrt(sum(a * a for a in u)) * math.sqrt(sum(b * b for b in v)) or 1.)
    return math.degrees(math.acos(max(-1., min(1., c))))


def eye_check(name, rows, near):
    """C: глаз порта к глазу PS2, пока порт на камере зоны (вне ±NEAR кадров у смен)"""
    ok = True
    for cam, ta, td in (('r1_cam1', 6., .6), ('z1_housejump', 1., .2)):
        A, D = [], []
        for r in rows:
            if r['cam'] != cam or any(abs(r['f'] - f) <= NEAR for f in near): continue
            if r['ps2'] is not None and r['ps2'] != NAME[cam]: continue
            ve = [a - b for a, b in zip(r['peye'], r['T'])]; vp = [a - b for a, b in zip(r['eye'], r['T'])]
            A.append(ang(ve, vp)); D.append(abs(math.dist(r['peye'], r['T']) - math.dist(r['eye'], r['T'])))
        if not A: continue
        ma, md = sum(A) / len(A), sum(D) / len(D); good = ma <= ta and md <= td; ok &= good
        print(f"  {'PASS' if good else 'FAIL'} {name} глаз {cam}: угол к PS2 {ma:.2f}° (≤ {ta}), дистанция {md:.2f} м (≤ {td}), строк {len(A)}")
    return ok


def check_types(name, rows):
    """A: тип камеры по строкам против SuperCamCentral PS2"""
    sp, sq = seq(rows, 'ps2'), seq(rows, 'port')
    trans = [(t, a) for t, a, _ in sp[1:]]
    ok = [t for t, _, _ in sp] == [t for t, _, _ in sq]
    print(f"{'PASS' if ok else 'FAIL'} {name}: PS2 {' '.join(f'{t}{a}–{b}' for t, a, b in sp)} | порт {' '.join(f'{t}{a}–{b}' for t, a, b in sq)}")
    good = True
    for t, f in trans:
        hit = [a for u, a, _ in sq[1:] if u == t and abs(a - f) <= NEAR]
        g = bool(hit); good &= g
        if not g: print(f"  FAIL {name}: смена PS2 на {t} в кадре {f} — у порта нет такой смены в ±{NEAR} кадра")
    bad = [r['f'] for r in rows if r['ps2'] != r['port'] and not any(abs(r['f'] - f) <= NEAR for _, f in trans)]
    if bad: print(f"  FAIL {name}: тип камеры расходится в {len(bad)} строках вне ±{NEAR} кадров у смен (первая {bad[0]})")
    near = [f for _, f in trans] + [a for _, a, _ in sq[1:]]
    return ok and good and not bad and eye_check(name, rows, near)


def check_speeds(name, rows, cut):
    """B: первая камера зоны и срезы глаза PS2"""
    sq = seq(rows, 'port'); zone = [(t, a) for t, a, _ in sq if t != 'F']
    first = zone[0] if zone else None
    ok = first is not None and first[0] == 'R' and abs(first[1] - cut) <= NEAR
    print(f"{'PASS' if ok else 'FAIL'} {name}: первая камера зоны порта {first[0] + str(first[1]) if first else '—'}, PS2 первый срез "
          f"на боковой ракурс {cut} (±{NEAR}) | порт {' '.join(f'{t}{a}–{b}' for t, a, b in sq)}")
    cuts = [r['f'] for i, r in enumerate(rows) if i and math.dist(r['eye'], rows[i - 1]['eye']) > 3.]
    sw = [a for _, a, _ in sq[1:]]
    for f in cuts:
        g = any(abs(f - a) <= NEAR for a in sw); ok &= g
        print(f"  {'PASS' if g else 'FAIL'} {name}: срез глаза PS2 в кадре {f} — смена камеры порта {'есть' if g else 'НЕТ'} в ±{NEAR}")
    return ok and eye_check(name, rows, cuts + sw)


def check_none(name, rows):
    """D: камер зон нет"""
    z = [r['f'] for r in rows if r['cam'] != '-']
    step = max(math.dist(r['eye'], rows[i - 1]['eye']) for i, r in enumerate(rows) if i)   # у PS2 срезов нет — камеры зоны нет
    ok = not z and step <= 3.
    print(f"{'PASS' if ok else 'FAIL'} {name}: камер зон порт {'не включал' if not z else f'включал в {len(z)} строках с кадра {z[0]}'} "
          f"(PS2 — камера за машиной весь прыжок: наибольший шаг глаза {step:.2f} м за строку, срез > 3), строк {len(rows)}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-D', action='append', default=[]); ap.add_argument('--out', default=str(ROOT / 'build/carzone/house_ps2'))
    ap.add_argument('--evidence-root')
    ap.add_argument('--pack', default=str(ROOT / 'build/ship_stage/carzone-l1.shr'))
    ap.add_argument('--legacy-listener', action='store_true', help='Historical diagnostic; not actual camera acceptance')
    a = ap.parse_args()
    if not a.legacy_listener:
        sys.path.insert(0,str(ROOT/'tests/camera'))
        from native_carzone import run
        a.old=False
        try:
            return run(a)
        except (ValueError,OSError) as e:
            print(str(e),file=sys.stderr)
            return 2
    print('INVALID CAMERA REFERENCE: legacy eye/cut fields used radSoundHalListener; diagnostic only')
    if not O4.is_dir(): print(f'FAIL нет записей PS2: {O4}'); return 2
    out = Path(a.out); tag = '_'.join(re.sub(r'\W', '', d) for d in a.D) or 'cur'
    exe = out / f'host_{tag}'; packf = out / 'carzone-l1.shr'
    build(a.D, exe); pack(packf)
    ok = True
    for run in ('ps2_v95_house_50_native', 'ps2_v95_house_70_native', 'ps2_v95_house_200_native',
                'ps2_v81_house50_reverse_exit', 'ps2_v81_house50_steer_exit'):
        ok &= check_types(run, replay(exe, packf, load_trace(run)))
    for row in fact('ps2-house-camera-speeds')['table']:
        ok &= check_speeds(row['id'], replay(exe, packf, load_trace(row['id'])), row['first_camera_cut_frame'])
    for row in fact('ps2-camera-after-landing')['table']:
        ok &= check_none(row['id'], replay(exe, packf, load_trace(row['id'])))
    ok &= check_none('codex378_jz2_0702', replay(exe, packf, load_codex378()))
    print('PASS carzone house/jump vs PS2' if ok else 'FAIL carzone house/jump vs PS2')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
