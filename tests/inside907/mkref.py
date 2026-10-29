#!/usr/bin/env python3
"""№907: эталон «из данных»: копия level.shr, где у кусков пропов и стейтпропов с пустым смешиванием (см. census.py) флаг 2 снят В ФАЙЛЕ
(не кодом движка). Картинка движка с правилом обязана совпасть с картинкой на этом файле. python mkref.py IN.shr OUT.shr"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import census
b = bytearray(Path(sys.argv[1]).read_bytes()); topq = census.tex_opaque(bytes(b)); props, sprops, city = census.pieces_of(bytes(b))
n = 0
for (tex, fl, nv, cnt, rec) in census.noop(bytes(b), topq, props) + census.noop(bytes(b), topq, sprops):
    fl0, = struct.unpack_from('<I', b, rec); struct.pack_into('<I', b, rec, fl0 & ~2); n += 1
Path(sys.argv[2]).write_bytes(bytes(b)); print('снят флаг 2 у %d кусков' % n)
