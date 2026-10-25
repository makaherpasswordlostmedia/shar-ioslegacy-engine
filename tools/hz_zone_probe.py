"""Разбор для зон дальности (№913): по ячейкам ленты (сетка 60 м, как horizon_export) считает, сколько в кольцах 130–150 и 150–250 м видно над ближним силуэтом, и открытость.
python3 hz_zone_probe.py LEVEL.shr OUT.npz [--cell 60]"""
import sys, argparse, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read, horizon_export as hx
ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('out'); ap.add_argument('--cell', type=float, default=60.)
a = ap.parse_args()
d = shr7read.load(a.level, far=False, owner=0)
keep = (d['FL'] & (1 | 2 | 4)) == 0
V = d['P'][keep].reshape(-1, 3); V = np.concatenate([V, d['P'][keep].mean(1)])
mn = V.min(0); mx = V.max(0)
xs = np.arange(np.floor(mn[0] / a.cell) * a.cell + a.cell / 2, mx[0], a.cell); zs = np.arange(np.floor(mn[2] / a.cell) * a.cell + a.cell / 2, mx[2], a.cell)
rows = []
NB = hx.NB
for x in xs:
    for z in zs:
        nb = V[np.hypot(V[:, 0] - x, V[:, 2] - z) < 15]
        if len(nb) < 4: continue
        ey = float(np.median(nb[:, 1])) + 2.
        near, _ = hx.skyline(V, x, ey, z, 3., 130.)
        r130, _ = hx.skyline(V, x, ey, z, 130., 150.)
        r250, _ = hx.skyline(V, x, ey, z, 150., 250.)
        nt = np.where(np.isnan(near), -0.05, np.maximum(near, -0.05))
        v130 = np.where(np.isnan(r130), 0., np.maximum(0., r130 - nt)); v250 = np.where(np.isnan(r250), 0., np.maximum(0., r250 - nt))
        openf = float(np.mean(np.isnan(near) | (near < 0.0)))   # доля азимутов без ближнего силуэта выше горизонта: открытый вид
        rows.append((x, z, ey, float(v130.mean()), float(v250.mean()), openf, float(np.mean(v130 > 0.02)), float(np.mean(v250 > 0.02))))
np.save(a.out, np.array(rows)); print(len(rows), 'ячеек ->', a.out)
