#!/usr/bin/env python3
"""Монета-спрайт (Роб 17.10): выгрузка настоящей 3D-монеты из level.shr (секция PRP2, тип coinType — ровно то, что рисует игра) для запекания в Blender.
    python3 tools/coin/coin_dump.py LEVEL.shr OUT_DIR  ->  OUT_DIR/coin.json (вершины в осях модели, UV, цвет вершин, треугольники), OUT_DIR/coin_tex.png
Вершина куска (viewer/main_state.h Vert, 16 Б): u, v (s16, /256 — UV в долях картинки), c (u32 ABGR), x, y, z (s16, модель = o + sc·v/32768), pad."""
import json, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tex_gate   # noqa: E402

def main(lvl, outd):
    b = Path(lvl).read_bytes(); outd = Path(outd); outd.mkdir(parents=True, exist_ok=True)
    if b[:4] != b'SHR7': raise SystemExit('не SHR7')
    po, = struct.unpack_from('<I', b, 96); h = b[po:po + 64]
    if h[:4] != b'PRP2': raise SystemExit('нет PRP2')
    npiece, ntype, ninst, vb, ib, ctype, ncoin = struct.unpack_from('<IIIIIiI', h, 4)
    q = po + 64; vbase = q; q += vb; ibase = q; q += ib
    pieces = [struct.unpack_from('<4f2i4I', b, q + 40 * i) for i in range(npiece)]; q += 40 * npiece
    types = [struct.unpack_from('<3f2I', b, q + 20 * i) for i in range(ntype)]
    if ctype < 0: raise SystemExit('в уровне нет монеты')
    _, _, _, first, n = types[ctype]
    recs, _, _, _ = tex_gate.walk(b)
    P, UV, C, T, texs = [], [], [], [], set()
    for k in range(first, first + n):
        ox, oy, oz, sc, tex, flags, nv, ni, voff, ioff = pieces[k]
        vv = np.frombuffer(b, np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')]), nv, vbase + voff)
        idx = np.frombuffer(b, '<u2', ni, ibase + ioff).astype(int) if not (flags & 16) else np.arange(nv)
        base = len(P)
        for v in vv:
            P.append([ox + sc * v['x'] / 32768.0, oy + sc * v['y'] / 32768.0, oz + sc * v['z'] / 32768.0]); UV.append([v['u'] / 256.0, v['v'] / 256.0])
            c = int(v['c']); C.append([(c & 255) / 255.0, ((c >> 8) & 255) / 255.0, ((c >> 16) & 255) / 255.0, (c >> 24) / 255.0])
        T += [[base + int(idx[i]), base + int(idx[i + 1]), base + int(idx[i + 2])] for i in range(0, len(idx) - 2, 3)]
        texs.add(tex); print(f'кусок {k}: текстура {tex}, флаги {flags}, вершин {nv}, индексов {ni}')
    if len(texs) != 1: print('ВНИМАНИЕ: текстур у монеты', texs)
    t = texs.pop(); img = tex_gate.level0(b, recs[t]); Image.fromarray(img, 'RGBA').save(outd / 'coin_tex.png')
    P = np.array(P); print(f'монета: вершин {len(P)}, треугольников {len(T)}, размах x {P[:, 0].min():.3f}..{P[:, 0].max():.3f} y {P[:, 1].min():.3f}..{P[:, 1].max():.3f} z {P[:, 2].min():.3f}..{P[:, 2].max():.3f}; текстура {t} {img.shape[1]}x{img.shape[0]}')
    (outd / 'coin.json').write_text(json.dumps(dict(P=P.tolist(), UV=UV, C=C, T=T)))

if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
