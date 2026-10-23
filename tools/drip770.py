#!/usr/bin/env python3
"""№770 (Роб 23.10: «там, где сверху капает типа кислота — сделать просто свет, чтобы из труб не капало, а был векторный свет: цилиндр сверху вниз,
сквозь него проезжаем, как конус; лагающие полупрозрачные капли убрать — они сильно бьют текстуры»): места капель из диска.
Капли — квадраты-билборды объектов Anim (0x3F0000C) в зонах уровня (L1/L4 l1z6/l4z6 — «goop»: шейдеры goop_m / goo_m — капли, glow2_m — свечение).
Для каждого квада капли — точка в мире (сустав в позе кадра 0 + сдвиг квада), координаты движка (z отзеркален, как prp2_export.billboards).
  python3 tools/drip770.py LEVEL OUT.bin   ->  'DRP1', u32 n, n × {f32 x, y, z (центр квада), u32 цвет, f32 ширина, высота квада} ; печать мест
Движок (viewer/spritelight.h drip770*): квады в 1,5 м от этих точек не рисует, рисует векторный цилиндр от точки до пола."""
import struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
from p3d import read          # noqa: E402
import prp2_export as PX       # noqa: E402
import animobj_export as AO    # noqa: E402
DRIP_SH = ('goop_m', 'goo_m')


def main():
    level, out = int(sys.argv[1]), Path(sys.argv[2])
    art = (ROOT / 'hit-and-run-web/source/game/art').resolve(); pts = []
    for f in PX.level_files(art, level):
        root = read(f)
        for ent in root.children:
            if ent.id != AO.ANIM: continue
            w = AO.gather(root, ent); bbs = PX.billboards(w)
            if not any(b['shader'].lower() in DRIP_SH for b in bbs.values()): continue
            props, _ = PX.composite(w); joints, *_ = PX.joint_poses(w); JW = PX.rest_world(joints)
            for dn, joint, trans in props:
                b = bbs.get(dn)
                if not b or b['shader'].lower() not in DRIP_SH: continue
                M = JW[joint] if joint < len(JW) else np.eye(4)
                for mode, t, col, wd, ht, dist in b['quads']:
                    p = (M @ np.array([t[0], t[1], t[2], 1.0]))[:3]
                    pts.append((float(p[0]), float(p[1]), float(p[2]), col, float(wd), float(ht)))
                    print(f'{f.stem}/{AO.N(ent)}/{dn} {b["shader"]} {mode} ({p[0]:.1f} {p[1]:.1f} {p[2]:.1f}) {wd:.2f}x{ht:.2f} {col:08x}')
    out.write_bytes(b'DRP1' + struct.pack('<I', len(pts)) + b''.join(struct.pack('<3fI2f', *q) for q in pts))
    print(f'уровень {level}: капель {len(pts)} -> {out}')


if __name__ == '__main__':
    main()
