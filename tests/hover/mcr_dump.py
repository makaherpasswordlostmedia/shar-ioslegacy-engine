#!/usr/bin/env python3
"""Правка 413б: куски и текстуры модели пакета машин миссий MCR1 (tools/msncar_export.py) — флаг 2 (полупрозрачное),
треугольники, альфа занятых цветов палитры (как viewer/main.c texOpaque: цвета точек верхнего уровня текстуры).
  python tests/hover/mcr_dump.py build/levels/l7/msncars-l7.shr frink_v"""
import struct, sys


def textures(b, off, size, n):
    out, p = [], off
    for _ in range(n):
        w, h, nl = struct.unpack_from('<3H', b, p); t4 = b[p + 6] == 4; sw = b[p + 7] == 1
        pal = struct.unpack_from('<256I', b, p + 16); q = p + 16 + 1024; lw, lh = w, h
        bw0 = (w + 1) // 2 if t4 else w; n0 = (16 if sw and bw0 < 16 else bw0) * (((h + 7) & ~7) if sw else h)
        ix = set(b[q:q + n0]) if not t4 else {v & 15 for v in b[q:q + n0]} | {v >> 4 for v in b[q:q + n0]}
        for _ in range(nl):
            bw = lw // 2 if t4 else lw
            q += (16 if sw and bw < 16 else bw) * (((lh + 7) & ~7) if sw else lh); q = (q + 15) & ~15
            lw, lh = max(lw >> 1, 1), max(lh >> 1, 1)
        a = [pal[i] >> 24 for i in sorted(ix)]   # как viewer/main.c texOpaque: только цвета, на которые ссылаются точки верхнего уровня
        out.append(dict(w=w, h=h, amin=min(a), opaque=min(a) == 255)); p = (q + 15) & ~15
    return out


def model(path, name):
    b = open(path, 'rb').read()
    magic, ver, lv, n, dir_off = struct.unpack_from('<4s4I', b, 0)
    for i in range(n):
        o = dir_off + 176 * i
        if b[o:o + 16].split(b'\0')[0].decode() != name: continue
        bo, bs, npc, vo, vb, to, tb, nt = struct.unpack_from('<8I', b, o + 16 + 128)
        tx = textures(b, bo + to, tb, nt)
        fp, np_, fl, nl = struct.unpack_from('<4H', b, o + 16 + 16)
        pcs = []
        for k in range(npc):
            po = bo + 80 * k; tex, flags, nv, ni = struct.unpack_from('<4i', b, po + 24); wheel, lod = struct.unpack_from('<2I', b, po + 72)
            pcs.append(dict(i=k, tex=tex, flags=flags, tris=ni // 3, wheel=wheel, near=fp <= k < fp + np_,
                            opaque_tex=tx[tex]['opaque'] if 0 <= tex < len(tx) else None, amin=tx[tex]['amin'] if 0 <= tex < len(tx) else None))
        return pcs, tx
    raise SystemExit(f'{name}: нет в {path}')


if __name__ == '__main__':
    pcs, tx = model(sys.argv[1], sys.argv[2])
    for p in pcs: print(p)
    near = [p for p in pcs if p['near']]
    print('near: tris', sum(p['tris'] for p in near), 'flag2', sum(p['tris'] for p in near if p['flags'] & 2),
          'flag2 and data-transparent', sum(p['tris'] for p in near if p['flags'] & 2 and not p['opaque_tex']))
