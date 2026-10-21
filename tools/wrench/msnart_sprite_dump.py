#!/usr/bin/env python3
"""Спрайты значков мира (Роб 18.10: «восклицательный знак над персонажами миссий и трубку над будкой — тем же способом, что монету и ключ:
кадры настоящей 3D-модели»): выгрузка составного рисунка из пакета msnart.shr (формат MSA2 — tools/msnart_export.py, viewer/msnart.c)
для tools/wrench/wrench_raster.py.
    python3 tools/wrench/msnart_sprite_dump.py MSNART.shr ИМЯ OUT_DIR  ->  OUT_DIR/coin.json (P, UV, C, T, TX), coin_tex*.png, info.json
Меши — в осях своего сустава в кадре 0 без поворота сустава (поза покоя: оборот спрайту даёт растеризатор), квады-свечения рисунка
(цвет, картинка, размер по кадрам) и ход суставов (подскок по высоте, угол поворота вокруг вертикали) — в info.json и в печать.
Данные игры — только чтение; выход — в build/ (ассеты не коммитить)."""
import json, math, struct, sys
from pathlib import Path
from PIL import Image

def main(pack, name, outd):
    outd = Path(outd); outd.mkdir(parents=True, exist_ok=True); B = Path(pack).read_bytes()
    assert B[:4] == b'MSA2', 'не MSA2'
    nrows, offrows = struct.unpack_from('<II', B, 4)
    for r in range(nrows):
        path = B[offrows + r * 96: offrows + r * 96 + 80].split(b'\0')[0].decode('latin-1'); off, size = struct.unpack_from('<II', B, offrows + r * 96 + 80)
        b = B[off: off + size]
        ntex, ndraw, nimg, oTex, oDraw, oImg = struct.unpack_from('<6I', b, 0)
        for k in range(ndraw):
            o = oDraw + k * 64; dn = b[o: o + 32].split(b'\0')[0].decode('latin-1')
            if dn.lower() != name.lower(): continue
            nbill, oBill, nmesh, oMesh, njoint, nfr = struct.unpack_from('<6I', b, o + 32); fps, = struct.unpack_from('<f', b, o + 56); oJoint, = struct.unpack_from('<I', b, o + 60)
            return dump(b, path, dn, ntex, oTex, nbill, oBill, nmesh, oMesh, njoint, nfr, fps, oJoint, outd)
    sys.exit(f'нет рисунка {name}')

def tex_png(b, oTex, ti, out):
    w, h, off, psm = struct.unpack_from('<HHII', b, oTex + ti * 16)
    Image.frombytes('RGBA', (w, h), b[off: off + w * h * 4]).save(out); return w, h

def dump(b, path, dn, ntex, oTex, nbill, oBill, nmesh, oMesh, njoint, nfr, fps, oJoint, outd):
    J = [[struct.unpack_from('<12f', b, oJoint + ((f * njoint) + j) * 48) for j in range(njoint)] for f in range(max(nfr, 1))] if njoint else []
    P, UV, C, T, TX, CUT, texmap, meshes, mj = [], [], [], [], [], [], {}, [], None
    for m in range(nmesh):
        tex, flags, nvert, oVert = struct.unpack_from('<4I', b, oMesh + m * 16); mode, j = (flags >> 8) & 0xFF, flags >> 16
        meshes.append({'tex': tex, 'mode': mode, 'joint': j, 'nvert': nvert})
        if mode >= 2: continue   # полупрозрачное и свечения — не тело значка (блик рисует общий рисовальщик)
        if tex not in texmap and tex < ntex: texmap[tex] = len(texmap); tex_png(b, oTex, tex, outd / f'coin_tex{"" if not texmap[tex] else texmap[tex]}.png')
        if mj is None: mj = j   # сустав меша 0: его центр рамки по кадрам клипа — центр спрайта в игре (msnart.c)
        base = len(P)
        for v in range(nvert):   # вершины — в осях сустава, как в пакете; позу кадра даёт icon_bake.py
            u, vv, c, x, y, z = struct.unpack_from('<ffIfff', b, oVert + v * 24)
            P.append([x, y, z]); UV.append([u, 1.0 - vv]); C.append([(c & 255) / 255, ((c >> 8) & 255) / 255, ((c >> 16) & 255) / 255, (c >> 24) / 255])
        for t in range(nvert // 3): T.append([base + 3 * t, base + 3 * t + 1, base + 3 * t + 2]); TX.append(texmap.get(tex, 0)); CUT.append(1 if mode == 1 else 0)
    (outd / 'coin.json').write_text(json.dumps({'P': P, 'UV': UV, 'C': C, 'T': T, 'TX': TX, 'CUT': CUT, 'ntex': len(texmap)}))
    bills = []
    for q in range(nbill):
        o = oBill + q * 80; tex, blend, mode, zw = struct.unpack_from('<4I', b, o); c = struct.unpack_from('<3f', b, o + 16)
        w, h = struct.unpack_from('<2f', b, o + 52); argb, bnf, oTr = struct.unpack_from('<3I', b, o + 60); bfps, dist = struct.unpack_from('<2f', b, o + 72)
        tr = [struct.unpack_from('<6f', b, oTr + f * 24) for f in range(max(bnf, 1))]
        if tex < ntex: tw, th = tex_png(b, oTex, tex, outd / f'bill{q}_tex{tex}.png')
        bills.append({'tex': tex, 'blend': blend, 'aax': mode & 255, 'joint': mode >> 8, 'zwrite': zw, 'c': c, 'w': w, 'h': h, 'argb': f'{argb:08x}', 'nfr': bnf, 'fps': bfps, 'dist': dist,
                      'track_min': [round(min(t[i] for t in tr), 3) for i in range(6)], 'track_max': [round(max(t[i] for t in tr), 3) for i in range(6)]})
    hop = [round(J[f][0][10], 3) for f in range(len(J))] if J else []
    ang = [round(math.degrees(math.atan2(-J[f][0][2], J[f][0][0])), 1) for f in range(len(J))] if J else []
    info = {'path': path, 'name': dn, 'nfr': nfr, 'fps': fps, 'njoint': njoint, 'meshes': meshes, 'bills': bills, 'joint0_y': hop, 'joint0_yaw_deg': ang,
            'mesh_joint': mj, 'mesh_joint_frames': [list(J[f][mj]) for f in range(len(J))] if J and mj is not None else [],
            'bbox': [[round(min(p[i] for p in P), 3) for i in range(3)], [round(max(p[i] for p in P), 3) for i in range(3)]] if P else None}
    (outd / 'info.json').write_text(json.dumps(info, ensure_ascii=False, indent=1))
    print(path, dn, 'кадров', nfr, 'fps', fps, 'суставов', njoint, 'мешей', nmesh, 'квадов', nbill, 'треуг', len(T), 'рамка', info['bbox'])
    if hop: print(' подскок y:', min(hop), '..', max(hop), ' поворот:', ang[:: max(1, len(ang) // 12)])
    for q in bills: print(' квад', q)

if __name__ == '__main__':
    main(*sys.argv[1:4])
