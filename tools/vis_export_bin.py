#!/usr/bin/env python3
"""npz выгрузки экспорта (SHR_PHANTOM_VOL_INPUTS) -> бинарь видимых треугольников для fence_vis_census.c: float32 x9 вершины + float32 ny. vis_export_bin.py NPZ OUT.bin"""
import sys, numpy as np
d = np.load(sys.argv[1], allow_pickle=True); T = d['vis'].astype(np.float64).reshape(-1, 3, 3)
n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); ny = n[:, 1] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
out = np.concatenate([T.reshape(-1, 9), ny[:, None]], 1).astype('<f4'); out.tofile(sys.argv[2]); print(len(T), 'треугольников')
