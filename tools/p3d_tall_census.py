#!/usr/bin/env python3
"""Перепись высоких мешей зон L1-L7 (только чтение диска): мировой габарит каждого меша, высота, превышение над окружением.
python3 -I tools/p3d_tall_census.py OUT.tsv   координаты p3d (z порта = -z)."""
import sys, pathlib, re
sys.path.insert(0, 'hit-and-run-web/tools')
import numpy as np
from p3d import read, walk, string
import convert
G = pathlib.Path('hit-and-run-web/source/game/art')
I = np.eye(4, dtype=np.float32)
def sname(c): return string(c.data)[0]
def mat(b, p): return np.frombuffer(b, dtype='<f4', count=16, offset=p).reshape(4, 4)
rows = []
for f in sorted(G.glob('l[1-7]z[1-4].p3d')):
    try: root = read(f)
    except Exception as e: print('ERR', f.name, e, file=sys.stderr); continue
    meshes = {sname(c): c for c in walk(root) if c.id == 0x10000}
    cache = {}
    def pts(name):
        if name not in cache:
            out = []
            for pg in meshes[name].children:
                if pg.id != 0x10002: continue
                try: _, parts = convert.geometry(pg)
                except Exception: continue
                for p in parts: out.append(p['position'])
            cache[name] = np.concatenate(out) if out else None
        return cache[name]
    placed = []
    def inst(c, M=I, iname=''):
        if c.id == 0x120103:
            iname, p = string(c.data); M = mat(c.data, p + 4) @ M
        if c.id == 0x120107:
            label, p = string(c.data); name, _ = string(c.data, p)
            if name in meshes: placed.append((name, M, label))
        for s in c.children: inst(s, M, iname)
    for c in root.children:
        if c.id == 0x3f00000:
            for m in c.children:
                if m.id == 0x10000: placed.append((sname(m), I, sname(m) + ' (static)'))
        elif c.id == 0x120100: inst(c)
        elif c.id in (0x3f00002, 0x3f0000a, 0x3f00009, 0x3f0000e, 0x3000008):
            for s in walk(c):
                if s.id == 0x3000008: inst(s)
    zone = []
    for name, M, label in placed:
        P = pts(name)
        if P is None or not len(P): continue
        W = (np.c_[P, np.ones(len(P), np.float32)] @ M)[:, :3]
        lo, hi = W.min(0), W.max(0)
        zone.append((name, label, lo, hi))
    if not zone: continue
    ground = np.median([z[2][1] for z in zone])
    for name, label, lo, hi in zone:
        rows.append((f.stem, name, label, *lo.round(1), *hi.round(1), round(float(hi[1] - lo[1]), 1), round(float(hi[1] - ground), 1)))
    print(f.name, len(zone), file=sys.stderr)
with open(sys.argv[1], 'w') as o:
    o.write('зона\tмеш\tэкземпляр\tminx\tminy\tminz\tmaxx\tmaxy\tmaxz\tвысота\tверх_над_медианой_низа\n')
    for r in rows: o.write('\t'.join(map(str, r)) + '\n')
