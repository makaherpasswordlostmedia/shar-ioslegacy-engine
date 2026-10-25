#!/usr/bin/env python3
"""№913: таблица зон дальности города (hzzone.bin рядом с horizon.shr). Зона клетки 60 м: 0 — 130 м, 1 — 150, 2 — 250.
Критерии по данным (hz_zone_probe.py, ящики с высоты глаза клетки): виды с высоты (глаз выше соседних клеток в 250 м), заметно торчащая над ближним силуэтом дальняя геометрия (кольца 130–150 и 150–250 м),
открытый вид (мало ближнего силуэта выше горизонта) — плюс явные места tools/hz_zone_places.json: {"3": [[x0, z0, x1, z1, зона], ...]}.
  hz_zones.py PROBE.npy OUT.bin [--level N] [--png OUT.png] [--cell 60]   формат HZN1: 'HZN1', w u32, h u32, x0, z0, шаг f32, w·h байт (255 — нет данных)"""
import sys, json, argparse, struct
from pathlib import Path
import numpy as np
T = dict(ey_hi=30., v130=.012, frac130=.12, v250=.025, frac250=.30, v250hi=.08, open_=.60)
def classify(rows, places, level, cell):
    xs = rows[:, 0]; zs = rows[:, 1]
    x0 = np.floor(xs.min() / cell) * cell; z0 = np.floor(zs.min() / cell) * cell
    w = int(np.ceil((xs.max() - x0) / cell)) + 1; h = int(np.ceil((zs.max() - z0) / cell)) + 1
    g = np.full((h, w), 255, np.uint8); why = {}
    ey = rows[:, 2]
    for i, (x, z, e, v1, v2, op, f1, f2) in enumerate(rows):
        near = (np.hypot(xs - x, zs - z) < 250.)
        exc = e - np.median(ey[near]); m = 0; r = ''
        if exc >= T['ey_hi'] or v2 >= T['v250hi']: m = 2; r = 'высота %.0f / дальнее %.3f' % (exc, v2)
        elif v1 >= T['v130'] or f1 >= T['frac130'] or v2 >= T['v250'] or f2 >= T['frac250'] or op >= T['open_']: m = 1; r = 'v130 %.3f f130 %.2f v250 %.3f f250 %.2f open %.2f' % (v1, f1, v2, f2, op)
        gx = int(np.floor((x - x0) / cell)); gz = int(np.floor((z - z0) / cell)); g[gz, gx] = m; why[(gx, gz)] = r
    # соседи без данных: ближайшая известная клетка (иначе 150 — как было)
    for (x0_, z0_, x1_, z1_, md) in places.get(str(level), []):
        for gz in range(h):
            for gx in range(w):
                cx, cz = x0 + gx * cell, z0 + gz * cell
                if x0_ <= cx <= x1_ and z0_ <= cz <= z1_ and (g[gz, gx] == 255 or g[gz, gx] < md): g[gz, gx] = md; why[(gx, gz)] = 'явное место'
    return x0, z0, w, h, g
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('probe'); ap.add_argument('out'); ap.add_argument('--level', type=int, default=0); ap.add_argument('--png'); ap.add_argument('--cell', type=float, default=60.)
    ap.add_argument('--places', default=str(Path(__file__).resolve().parent / 'hz_zone_places.json'))
    a = ap.parse_args(); rows = np.load(a.probe); places = json.loads(Path(a.places).read_text()) if Path(a.places).exists() else {}
    x0, z0, w, h, g = classify(rows, places, a.level, a.cell)
    Path(a.out).write_bytes(b'HZN1' + struct.pack('<IIfff', w, h, x0, z0, a.cell) + g.tobytes())
    n = (g != 255).sum(); print('уровень %d: клеток %d, 130 м: %d (%.0f %%), 150 м: %d (%.0f %%), 250 м: %d (%.0f %%)' % (a.level, n, (g == 0).sum(), 100 * (g == 0).sum() / max(1, n), (g == 1).sum(), 100 * (g == 1).sum() / max(1, n), (g == 2).sum(), 100 * (g == 2).sum() / max(1, n)))
    if a.png:
        from PIL import Image
        im = np.zeros((h, w, 3), np.uint8); im[g == 0] = (60, 160, 90); im[g == 1] = (230, 180, 40); im[g == 2] = (210, 60, 60); im[g == 255] = (30, 30, 30)
        Image.fromarray(im[::-1]).resize((w * 8, h * 8), Image.NEAREST).save(a.png)
