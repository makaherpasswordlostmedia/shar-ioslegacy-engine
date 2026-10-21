#!/usr/bin/env python3
"""№408: default gate uses archived typed tPointCamera, not the sound listener.

Run with python3.14 --pack build/ship_stage/carzone-l1.shr. Red control:
-D CARZONE_LISTENER_OLD=1 restores the erroneous 10m clamp; CARZONE_PS2_OLD=1
tests accepted trigger/type behavior independently. All original P2S/trace SHAs
are validated. The historical diagnostic below requires --legacy-listener,
returns rc2 and cannot accept rendering-camera behavior.

Historical listener diagnostic (superseded):

Траектория машины оригинала из записей близнеца (build/codex-terminal/rob-rest/378/attempt1, дом с трамплином jumpzone17 L1,
famil_v, 50 Гц, строки через 2 кадра; положение — начало модели, тангаж — jump.tsv) подаётся в настоящий carZoneStep (+ roomcam.c)
с пакетом камер уровня 1 прямо с диска; кузов — коробка famil_v (car.c carDefaults: полуширина 1,10, полудлина 2,675, сдвиг −0,32,
днище 0,28 и крыша 1,65 над землёй; земля — 0,70 м под началом модели, knowledge/facts/ps2-ramps.yaml). Сверка с глазом камеры PS2
(блок 0x7aaba0) в той же строке:
  native2 (газ до упора, 107 км/ч, перелёт дома): PS2 включает рельс r1_cam1 срезом в кадре 932 и выключает в 1016;
  k50 (50 км/ч, удар в стену дома): рельс НЕ включается, статичная z1_housejump включается срезом в кадре 1048 и держит до конца.
Зелёный: вход и выход в ±4 кадра от PS2; пока PS2 снимает камерой зоны, у порта та же камера, угол глаза от машины к PS2 в среднем
≤ 6° (рельс) / ≤ 1° (статичная) и дистанция ≤ 0,6 / 0,2 м; в k50 рельс ни разу не включился.

  python3 tests/camera/carzone_ps2.py                  зелёный
  python3 tests/camera/carzone_ps2.py --old            красный: прежний порт (камер зон у машины нет — снимает камера за машиной)
  python3 tests/camera/carzone_ps2.py -D CARZONE_RAIL_MINV=0     красный: рельс у любой скорости (k50 включает r1_cam1)
  python3 tests/camera/carzone_ps2.py -D CARZONE_DIST=1000       красный: глаз в месте камеры (без 10 м)"""
import argparse, math, re, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'build/codex-terminal/rob-rest/378/attempt1'
HALF_W, HALF_L, OFS, LO, HI, ORIGIN = 1.10, 2.675, -0.32, 0.28, 1.65, 0.70

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
    if (k >= 0) printf("%s %.4f %.4f %.4f %.4f %.4f %.4f %.2f\n", cams[k].name, eye[0], eye[1], eye[2], look[0], look[1], look[2], fy);
    else printf("- 0 0 0 0 0 0 0\n");
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


def load(run):
    J = {int(float(l.split('\t')[0])): l.rstrip('\n').split('\t') for l in (RUNS / run / 'jump.tsv').read_text().splitlines()[1:]}
    rows = []
    for l in (RUNS / run / 'camera.tsv').read_text().splitlines()[1:]:
        r = [float(v) for v in l.split('\t')]
        f = int(r[0]); j = J.get(f)
        rows.append(dict(f=f, p=tuple(r[1:4]), fw=(r[4], r[5]), eye=tuple(r[7:10]), v=float(j[5]) if j and j[5] else 0.,
                         pitch=math.radians(float(j[10])) if j and j[10] else 0.))
    return rows


def body(r):
    """коробка кузова (центр и 8 углов) в осях движка (z отзеркален)"""
    fx, fz = r['fw'][0], -r['fw'][1]; ln = math.hypot(fx, fz) or 1.; fx /= ln; fz /= ln
    ox, oy, oz = r['p'][0], r['p'][1] - ORIGIN, -r['p'][2]; sl = math.tan(r['pitch'])
    cx, cz = ox + fx * OFS, oz + fz * OFS
    pts = [(cx, oy + OFS * sl + (LO + HI) / 2, cz)]
    for a in (-HALF_L, HALF_L):
        for b in (-HALF_W, HALF_W):
            for h in (LO, HI):
                x, z = cx + fx * a - fz * b, cz + fz * a + fx * b
                pts.append((x, oy + (OFS + a) * sl + h, z))
    return pts


def replay(exe, packf, rows):
    lines = []
    for i, r in enumerate(rows):
        dt = 2 / 50. if i else 1 / 50.
        a = rows[max(0, i - 1)]; b = rows[min(len(rows) - 1, i + 1)]; span = (b['f'] - a['f']) / 50. or 1.
        sp = math.hypot(b['p'][0] - a['p'][0], b['p'][2] - a['p'][2]) / span
        ref = (r['p'][0], r['p'][1], -r['p'][2])
        lines.append(f"{dt:.5f} {ref[0]:.4f} {ref[1]:.4f} {ref[2]:.4f} {sp:.4f} " + ' '.join(f'{x:.4f} {y:.4f} {z:.4f}' for x, y, z in body(r)))
    out = subprocess.run([str(exe), str(packf)], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout.split('\n')
    res = []
    for r, o in zip(rows, out):
        t = o.split(); name = t[0]
        e = (float(t[1]), float(t[2]), -float(t[3]))
        res.append((name, e))
    return res


def ps2_zone(rows):
    """кадры, где PS2 снимает камерой зоны: глаз сбоку от курса машины > 12° или стоит, пока машина едет (по записи)"""
    out = []
    for r in rows:
        dx, dz = r['eye'][0] - r['p'][0], r['eye'][2] - r['p'][2]
        side = math.degrees(math.atan2(dx * r['fw'][1] - dz * r['fw'][0], -(dx * r['fw'][0] + dz * r['fw'][1])))
        out.append(abs(side) > 12.)
    return out


def ang(u, v):
    c = sum(a * b for a, b in zip(u, v)) / (math.sqrt(sum(a * a for a in u)) * math.sqrt(sum(b * b for b in v)) or 1.)
    return math.degrees(math.acos(max(-1., min(1., c))))


def check(name, rows, res, want_cam, on_ps2, off_ps2, tol_ang, tol_d, old):
    ok = True
    on = [r['f'] for r, (n, _) in zip(rows, res) if n != '-']
    names = sorted({n for n, _ in res if n != '-'})
    first = on[0] if on else None
    last = None
    if on:   # первый выход после первого входа
        idx = [i for i, (n, _) in enumerate(res) if n != '-']; j = idx[0]
        while j < len(res) and res[j][0] != '-': j += 1
        last = rows[j]['f'] if j < len(res) else None
    def near(a, b): return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 4)
    good = near(first, on_ps2) and near(last, off_ps2) and names == [want_cam]
    print(f"{'PASS' if good else 'FAIL'} {name}: камера зоны порта {names or '—'} с {first} по {last}, PS2 {want_cam} с {on_ps2} по {off_ps2}")
    ok &= good
    A, D = [], []
    for r, (n, e) in zip(rows, res):
        if not (on_ps2 <= r['f'] < (off_ps2 or 1 << 30)): continue
        p = r['p']
        if old or n == '-':   # прежний порт: камера за машиной (позади по курсу, 10 м и 3,4 м выше — дальний вариант famil_v)
            e = (p[0] - r['fw'][0] * 9.66, p[1] + 3.43, p[2] - r['fw'][1] * 9.66)
        ve = [a - b for a, b in zip(e, p)]; vp = [a - b for a, b in zip(r['eye'], p)]
        A.append(ang(ve, vp)); D.append(abs(math.sqrt(sum(x * x for x in ve)) - math.sqrt(sum(x * x for x in vp))))
    ma, md = sum(A) / len(A), sum(D) / len(D)
    good = ma <= tol_ang and md <= tol_d
    print(f"{'PASS' if good else 'FAIL'} {name}: глаз от машины к глазу PS2 — угол {ma:.2f}° (≤ {tol_ang}), дистанция {md:.2f} м (≤ {tol_d}), кадров {len(A)}")
    return ok and good


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', action='store_true'); ap.add_argument('-D', action='append', default=[])
    ap.add_argument('--out', default=str(ROOT / 'build/camera/carzone_ps2'))
    ap.add_argument('--evidence-root')
    ap.add_argument('--pack', default=str(ROOT / 'build/ship_stage/carzone-l1.shr'))
    ap.add_argument('--legacy-listener', action='store_true', help='Historical diagnostic only, never camera acceptance')
    a = ap.parse_args()
    if not a.legacy_listener:
        from native_carzone import run
        try:
            return run(a)
        except (ValueError, OSError) as e:
            print(str(e), file=sys.stderr)
            return 2
    print('INVALID CAMERA REFERENCE: legacy 0x7aaba0 is radSoundHalListener; diagnostic only')
    out = Path(a.out); tag = '_'.join(re.sub(r'\W', '', d) for d in a.D) or 'cur'
    exe = out / f'host_{tag}'; packf = out / 'carzone-l1.shr'
    build(a.D + (['CARZONE_OFF'] if a.old else []), exe); pack(packf)
    ok = True
    rows = load('original-house-native2'); res = replay(exe, packf, rows)
    if a.old: res = [('-', e) for _, e in res]
    ok &= check('native2 107 км/ч', rows, res, 'r1_cam1', 932, 1016, 6., .6, a.old)
    rows = load('original-house-k50'); res = replay(exe, packf, rows)
    if a.old: res = [('-', e) for _, e in res]
    ok &= check('k50 50 км/ч', rows, res, 'z1_housejump', 1048, None, 1., .2, a.old)
    print('PASS carzone vs PS2' if ok else 'FAIL carzone vs PS2')
    return 2  # A listener diagnostic cannot accept actual camera behavior.


if __name__ == '__main__':
    raise SystemExit(main())
