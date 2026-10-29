#!/usr/bin/env python3
"""Карта «сколько треугольников города рисует PSP» по клеткам PVS (для ночной оценки кадра PSP, 11.10).
  python3 tools/bots/city_tris.py LEVEL.shr OUT.tsv [дальность 250]
Модель как tools/pvs_frame_est.py (дисплей-лист клетки целиком + прозрачные куски, конус и дальность камеры сзади-сверху машины,
4 курса), берётся ХУДШИЙ из 4 курсов и среднее. Строка: x z ктреуг_среднее ктреуг_худшее вызовов_среднее."""
import sys, struct
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1])); import budget as B
path, out = sys.argv[1], sys.argv[2]; draw = float(sys.argv[3]) if len(sys.argv) > 3 else 250.
L = B.load(path); recs = L['recs']
own = np.array([r['owner'] for r in recs]); bb = np.array([r['bb'] for r in recs]); c = (bb[:, :3] + bb[:, 3:]) / 2
rad = .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1); ni = np.array([r['ni'] for r in recs]) // 3; fl = np.array([r['flags'] for r in recs])
d = open(path, 'rb').read(); off = struct.unpack_from('<I', d, 88)[0]
ox, oz, cell = struct.unpack_from('<3f', d, off + 4); W, H, pool, pad = struct.unpack_from('<4I', d, off + 16)
ent = np.frombuffer(d, '<u4', 2 * W * H, off + 32).reshape(-1, 2); pl = np.frombuffer(d, '<u2', pool, off + 32 + 8 * W * H)
cellid = np.array([r['cell'] for r in recs]); opaque = (fl & 2) == 0; ncell = int(cellid[own == 0].max()) + 1
cell_tris = np.bincount(cellid[(own == 0) & opaque], weights=ni[(own == 0) & opaque], minlength=ncell)
hm = L['hm']; rows = []
for gz in range(H):
    for gx in range(W):
        s, n = ent[gz * W + gx]
        if n == 0xFFFFFFFF or n == 0: continue
        lst = pl[s:s + n]; x = ox + (gx + .5) * cell; z = oz + (gz + .5) * cell
        hx = int((x - L['hox']) // L['cell']); hz = int((z - L['hoz']) // L['cell'])
        if not (0 <= hx < L['W'] and 0 <= hz < L['H']): continue
        hs = hm[hz, hx]; hs = hs[hs != -32768]
        if not len(hs): continue
        y = hs.min() * .01; m = np.zeros(len(recs), bool); m[lst] = True; vals = []; calls = []
        for h in np.arange(0, 2 * np.pi, np.pi / 2):
            e = np.array([x - np.sin(h) * 7.5, y + 3.2, z - np.cos(h) * 7.5]); f = np.array([x, y + 1.4, z]) - e; f /= np.linalg.norm(f)
            dv = c - e; dist = np.linalg.norm(dv, axis=1); fw = dv @ f; side = np.sqrt(np.maximum(0, dist ** 2 - fw ** 2))
            inf = (dist - rad <= draw) & ~(side * .60 - fw * .80 > rad) & (own == 0) & m
            cells = np.unique(cellid[inf & opaque]); vals.append(cell_tris[cells].sum() + ni[inf & ~opaque].sum()); calls.append(len(cells) + (inf & ~opaque).sum())
        rows.append((x, z, np.mean(vals) / 1e3, max(vals) / 1e3, np.mean(calls)))
with open(out, 'w') as o:
    o.write('# x\tz\tktris_mean\tktris_worst\tcalls_mean\n')
    for r in rows: o.write('%.1f\t%.1f\t%.2f\t%.2f\t%.0f\n' % r)
print(f'{path}: клеток {len(rows)}, ктреуг среднее {np.mean([r[2] for r in rows]):.1f}, худшее {max(r[3] for r in rows):.1f}')
