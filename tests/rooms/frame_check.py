#!/usr/bin/env python3
"""Правка 138 (Роб 01.10: «ракурсы камер внутри помещений — как в оригинале, локаторы держали камеру»): Гомер в кадре
камеры комнаты на всём достижимом полу. Независимо от движка: пол — треугольники земли COL1 файла комнаты с диска
(нормаль y > 0,7), мебель — ящики, раздутые на радиус Гомера 0,3 м; заливка от InteriorEntryEnd шагом 0,2 м, каждая 7-я
точка. Движок (tests/rooms/frame_host.c на viewer/roomcam.c) выбирает камеру и считает глаз и цель; проверка — грудь
Гомера (ноги + 1,0 м) внутри кадра 16:9 при вертикальном FOV камеры (Hor+, как viewer/main.c).
  frame_check.py points ВЫХОД.txt              записать точки пола комнат уровня 1
  frame_check.py check ХОСТ.txt [--min-miss N]  PASS — промахов 0 и нет точек без камеры; с --min-miss: PASS, если промахов ≥ N"""
import sys, math
from collections import deque, defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
ART = (ROOT / 'hit-and-run-web/source/game/art').resolve()
ROOMS = {'l1i00': 'SpringfieldElementary', 'l1i01': 'KwikEMart', 'l1i02': 'SimpsonsHouse'}
R0, STEP, EVERY = 0.3, 0.2, 7


def reach(stem):
    import psp_export as PE, interior_export as IE
    from p3d import read
    f = ART / f'{stem}.p3d'
    start = next(l for l in IE.locators(f) if l['name'] == 'InteriorEntryEnd')['pos']
    TR, BX, CY, SG, rep = PE.col_collect([(stem, read(f))])
    TR = np.array(TR, float); BX = np.array(BX, float)
    floor = TR[TR[:, 3, 1] > 0.7][:, :3]; y0 = floor[:, :, 1].min(); floor = floor[floor[:, :, 1].mean(1) <= y0 + 0.6]
    x0, z0 = floor[:, :, 0].min() - 1, floor[:, :, 2].min() - 1
    xs = np.arange(x0, floor[:, :, 0].max() + 1, STEP); zs = np.arange(z0, floor[:, :, 2].max() + 1, STEP)
    X, Z = np.meshgrid(xs + STEP / 2, zs + STEP / 2, indexing='ij'); flo = np.zeros(X.shape, bool)
    for t in floor:
        a, b, c = t[:, [0, 2]]; v0 = c - a; v1 = b - a; P = np.stack([X - a[0], Z - a[1]], -1)
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1; d20, d21 = P @ v0, P @ v1; den = d00 * d11 - d01 * d01
        if abs(den) < 1e-12: continue
        u = (d11 * d20 - d01 * d21) / den; v = (d00 * d21 - d01 * d20) / den; flo |= (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
    blk = np.zeros(X.shape, bool); yb = y0 + 0.9
    for bx in BX:
        c = bx[0:3]; ax = bx[3:12].reshape(3, 3); h = bx[12:15]
        d = np.stack([X - c[0], np.full(X.shape, yb - c[1]), Z - c[2]], -1); ins = np.ones(X.shape, bool)
        for j in range(3): ins &= np.abs(d @ ax[j]) <= h[j] + (R0 if abs(ax[j][1]) < 0.9 else 0)
        blk |= ins
    s = (int((start[0] - x0) / STEP), int((start[2] - z0) / STEP)); seen = np.zeros_like(blk); q = deque([s]); seen[s] = True
    while q:
        i, k = q.popleft()
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, k + dk
            if 0 <= a < len(xs) and 0 <= b < len(zs) and not seen[a, b] and flo[a, b] and not blk[a, b]: seen[a, b] = True; q.append((a, b))
    return [(X[i, k], y0, Z[i, k]) for i, k in zip(*np.nonzero(seen))]


def inframe(eye, look, fovy, q):
    f = np.array(look) - np.array(eye); f /= np.linalg.norm(f); r = np.cross(f, [0, 1.0, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    tv = math.tan(math.radians(fovy) / 2); th = tv * 16 / 9; d = np.array(q) - np.array(eye); z = d @ f
    return z > 0.05 and abs(d @ r / z) <= th and abs(d @ u / z) <= tv


def main():
    if sys.argv[1] == 'points':
        with open(sys.argv[2], 'w') as o:
            for stem, room in ROOMS.items():
                P = reach(stem)
                for p in P[::EVERY]: o.write(f'{room} {p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\n')
                print(f'{room}: пол {len(P)} точек, проверяется {len(P[::EVERY])}')
        return 0
    miss, tot, nocam = defaultdict(int), defaultdict(int), 0
    for ln in open(sys.argv[2]):
        w = ln.split()
        if w[0] != 'P': print('хост:', ln.strip()); return 1
        room, p, cam, fy = w[1], [float(v) for v in w[2:5]], int(w[5]), float(w[7])
        if cam < 0: nocam += 1; continue
        e, l = [float(v) for v in w[8:11]], [float(v) for v in w[11:14]]; key = f'{room}/{w[14]}'
        tot[key] += 1; miss[key] += not inframe(e, l, fy, (p[0], p[1] + 1.0, p[2]))
    # правка 186 (близнец v17_house_cam / v11_kwik_fwd, tests/rooms/roomcam_twins.py): рельсы TrackRail 1 у оригинала смотрят
    # вдоль рельса постоянным направлением — Гомер у них может выйти из кадра, как в PS2; с --skip-track они только в отчёте
    track = set()
    if '--skip-track' in sys.argv:
        sys.path.insert(0, str(ROOT / 'tests/rooms')); import cams_check as CC
        for stem, room in ROOMS.items(): track |= {f"{room}/{c['name']}" for c in CC.cameras(stem) if c['type'] == 1 and c.get('track')}
    for k in sorted(tot): print(f'  {k}: грудь вне кадра {miss[k]}/{tot[k]}' + ('  (TrackRail 1 — вдоль рельса, как у PS2; не в счёт)' if k in track else ''))
    m = sum(v for k, v in miss.items() if k not in track); print(f'итого промахов {m} из {sum(v for k, v in tot.items() if k not in track)}, точек без камеры {nocam}')
    if '--min-miss' in sys.argv: ok = m >= int(sys.argv[sys.argv.index('--min-miss') + 1])
    else: ok = m == 0 and nocam == 0
    print('PASS' if ok else 'FAIL'); return 0 if ok else 1


if __name__ == '__main__': sys.exit(main())
