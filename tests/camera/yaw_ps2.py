#!/usr/bin/env python3
"""№407: поворот камеры за машиной против записи PS2 (build/twins/o4/v28_drive_cam/drive.tsv, 50 Гц, 1500 кадров с поворотами).
Курс машины оригинала подаётся в ту же критически затухающую пружину, что viewer/main.c chaseCamUpdate (cdStep, ω = CAM_YAW_W из
main.c), и сравнивается с курсом камеры оригинала (от камеры к машине). Зелёный: средняя ошибка ≤ 0,6°, p95 ≤ 2°.
  python3 tests/camera/yaw_ps2.py            текущая жёсткость из main.c
  python3 tests/camera/yaw_ps2.py --w 6      красный: прежняя (обязан упасть)"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import math, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
w = float(sys.argv[sys.argv.index('--w') + 1]) if '--w' in sys.argv else \
    float(re.search(r'#define CAM_YAW_W ([0-9.]+)f', read_main(ROOT / 'viewer/main.c')).group(1))
rows = [l.rstrip('\n').split('\t') for l in open(ROOT / 'build/twins/o4/v28_drive_cam/drive.tsv')][1:]
wrap = lambda a: (a + math.pi) % (2 * math.pi) - math.pi
H = [math.radians(float(r[4])) for r in rows]; V = [float(r[5]) for r in rows]
C = [math.atan2(float(r[1]) - float(r[9]), float(r[3]) - float(r[11])) for r in rows]
dt, sub = 2 / 50, 8
y, yv, err = C[0], 0., []
for h, c, v in zip(H, C, V):
    for _ in range(sub):   # cdStep: точное решение критически затухающей пружины на шаге
        e = wrap(y - h); t = dt / sub; ex = math.exp(-w * t); tmp = (yv + w * e) * t
        yv = (yv - w * tmp) * ex; e = (e + tmp) * ex; y = wrap(h + e)
    if v > 3: err.append(abs(math.degrees(wrap(y - c))))
err.sort(); mean = sum(err) / len(err); p95 = err[int(len(err) * .95)]
ok = mean <= .6 and p95 <= 2.
print(f"{'PASS' if ok else 'FAIL'} camera yaw vs PS2: omega {w}, frames {len(err)}, mean {mean:.2f} deg, p95 {p95:.2f} deg")
sys.exit(0 if ok else 1)
