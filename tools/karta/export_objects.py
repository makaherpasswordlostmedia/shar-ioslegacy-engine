#!/usr/bin/env python3
"""level.shr (SHR7) -> levels/lN_obj.json: пропы PRP1 и стейтпропы SPR1 как ориентированные коробки (для слоя «объекты» на карте).
Только чтение level.shr. Формат: {"p":[[x,y,z,qx,qy,qz,qw,cx,cy,cz,hx,hy,hz,тип],...], "s":[... то же ...]};
номер объекта = индекс в своём массиве (p = экземпляр PRP1, s = экземпляр SPR1)."""
import sys, json, struct
from pathlib import Path
import numpy as np

PKG = Path.home() / 'Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721'
OUT = Path(__file__).parent / 'levels'

def objects(b):
    o, = struct.unpack_from('<I', b, 96)
    res = dict(p=[], s=[])
    if not o or b[o:o + 4] not in (b'PRP1', b'PRP2'): return res
    npiece, ntype, ninst, vb, ib = struct.unpack_from('<5I', b, o + 4)
    H = 64 if b[o:o + 4] == b'PRP2' else 32
    vbase = o + H
    pp = vbase + vb + ib
    pieces = [struct.unpack_from('<4f2i4I', b, pp + 40 * i) for i in range(npiece)]
    p = pp + 40 * npiece
    types = [struct.unpack_from('<3f2I', b, p + 20 * i) for i in range(ntype)]; p += 20 * ntype
    # локальная коробка типа: по вершинам его кусков (вершина: u,v,c4, x,y,z int16, pad)
    box = []
    for radius, halfH, mass, first, n in types:
        lo = np.full(3, 1e9); hi = np.full(3, -1e9)
        for i in range(first, first + n):
            ox, oy, oz, sc, tex, fl, nv, ni, vOff, iOff = pieces[i]
            if not nv: continue
            v = np.frombuffer(b, np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('xyz', '<i2', 3), ('pad', '<i2')]), nv, vbase + vOff)
            P = v['xyz'].astype(float) / 32767 * sc + np.array([ox, oy, oz])
            lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0))
        if lo[0] > hi[0]: lo = np.array([-radius, -halfH, -radius]); hi = -lo
        box.append((((lo + hi) / 2).tolist(), ((hi - lo) / 2).tolist()))
    for i in range(ninst):
        x, y, z, w, qx, qy, qz, ty = struct.unpack_from('<3f4fI', b, p + 32 * i)
        c, h = box[ty] if ty < len(box) else ([0, 0, 0], [.5, .5, .5])   # ty — физический тип ATC; если вне таблицы — запасной куб
        res['p'].append([x, y, z, qx, qy, qz, w] + c + h + [int(ty), types[ty][0], types[ty][1]] if ty < len(types) else [x, y, z, qx, qy, qz, w] + c + h + [int(ty), .5, .5])
    if b[o:o + 4] == b'PRP2':
        s = o + struct.unpack_from('<I', b, o + 32)[0]
        ntp, nin, npc2, nj, nk, nvis, nst, nev, ncall, ncol, nbill, vb2, ib2 = struct.unpack_from('<13I', b, s + 4)
        q = s + 64
        def adv(q, n): q += n; return q + (-(q - s) % 16)
        q = adv(adv(q, vb2), ib2)
        q = adv(q, 40 * npc2)
        tq = q
        for n in (84 * ntp, 52 * nj, 28 * nk, 4 * nvis, 80 * nst, 4 * nev, 8 * ncall, 64 * ncol, 40 * nbill): q = adv(q, n)
        # тип: kind @24 (u16), c @60, h @72
        for i in range(nin):
            x, y, z, qw, qx, qy, qz, ty, tag = struct.unpack_from('<7f2H', b, q + 32 * i)
            kind, = struct.unpack_from('<H', b, tq + 84 * ty + 24)
            c = struct.unpack_from('<3f', b, tq + 84 * ty + 60); h = struct.unpack_from('<3f', b, tq + 84 * ty + 72)
            if max(h) <= 0: h = (.5, .5, .5)
            res['s'].append([x, y, z, qx, qy, qz, qw, *c, *h, int(ty)])
    return res

if __name__ == '__main__':
    for n in sys.argv[1:]:
        path = PKG / ('level.shr' if n == '1' else f'l{n}/level.shr')
        r = objects(path.read_bytes())
        r = {k: [[round(v, 3) for v in row[:13]] + [int(row[13])] + [round(v, 3) for v in row[14:]] for row in rows] for k, rows in r.items()}
        (OUT / f'l{n}_obj.json').write_text(json.dumps(r, separators=(',', ':')))
        print('L' + n, 'p', len(r['p']), 's', len(r['s']), flush=True)
