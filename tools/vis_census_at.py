#!/usr/bin/env python3
"""Видимая геометрия вокруг точки по выгрузке экспорта (SHR_PHANTOM_VOL_INPUTS .npz: vis — рисуемые треугольники города, vtx — текстуры). vis_census_at.py NPZ x y z [R] [x2 z2 — отрезок забора].
Печатает: сколько видимых стен (|n.y| < 0.5) в слое [y, y+2.2] в радиусе R, расстояние до ближайшей, их высоту и текстуры; для отрезка — расстояние от его точек до ближайшей видимой стены."""
import sys, numpy as np
d = np.load(sys.argv[1], allow_pickle=True); x, y, z = map(float, sys.argv[2:5]); R = float(sys.argv[5]) if len(sys.argv) > 5 else 6.0
T = d['vis'].astype(np.float64).reshape(-1, 3, 3); tx = d['vtx']
n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(n, axis=1); nn = n / np.maximum(nl, 1e-12)[:, None]
c = T.mean(1); ymin = T[:, :, 1].min(1); ymax = T[:, :, 1].max(1)
near = (np.hypot(c[:, 0] - x, c[:, 2] - z) <= R + 3) & (ymax >= y - 0.3) & (ymin <= y + 2.2)
wall = near & (np.abs(nn[:, 1]) < 0.5)
idx = np.nonzero(wall)[0]
print(f"видимых треугольников в слое: {int(near.sum())}, из них стен: {len(idx)}")
if len(idx):
    dist = np.hypot(c[idx, 0] - x, c[idx, 2] - z); o = np.argsort(dist)[:8]
    for k in o: i = idx[k]; print(f"  стена: расст. {dist[k]:.1f} м центр({c[i,0]:.1f} {c[i,1]:.1f} {c[i,2]:.1f}) y {ymin[i]:.2f}..{ymax[i]:.2f} тексура {int(tx[i])} n({nn[i,0]:.2f} {nn[i,1]:.2f} {nn[i,2]:.2f})")
    print("  текстур у стен:", dict(zip(*np.unique(tx[idx], return_counts=True))))
if len(sys.argv) > 7:
    a = np.array([float(sys.argv[6]), float(sys.argv[7])])
    b = np.array([float(sys.argv[8]), float(sys.argv[9])]) if len(sys.argv) > 9 else a
    for t in np.linspace(0, 1, 6):
        p = a + (b - a) * t
        dd = np.hypot(c[idx, 0] - p[0], c[idx, 2] - p[1]) if len(idx) else np.array([1e9])
        print(f"  точка забора ({p[0]:.1f} {p[1]:.1f}): ближайшая видимая стена {dd.min():.1f} м")
