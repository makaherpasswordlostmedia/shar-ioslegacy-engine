#!/usr/bin/env python3
"""Место машины для сцены щита (tests/levelmech/emu.sh shield): 6 м к югу от осы со щитом из пакета CLT1, курс 0.
  wasp_pos.py collect-lN.shr [имя осы]  ->  "x z курс" или пусто, если ос со щитом нет"""
import struct, sys
b = open(sys.argv[1], 'rb').read(); u = struct.unpack_from('<15I', b, 4); want = sys.argv[2] if len(sys.argv) > 2 else ''; best = None
for i in range(u[8]):
    o = u[9] + 80 * i; name = b[o:o + 16].split(b'\0')[0].decode(); x, y, z = struct.unpack_from('<3f', b, o + 16)
    fl, = struct.unpack_from('<H', b, o + 66)
    if fl & 2 and (best is None or name == want): best = (x, z)
    if name == want and fl & 2: break
print(f'{best[0]:.2f} {best[1] - 6.0:.2f} 0.0000' if best else '')
