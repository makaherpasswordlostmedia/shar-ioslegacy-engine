#!/usr/bin/env python3
"""№907-город: эталон «из данных»: копия level.shr, где у кусков города по правилу (city.plan) флаг 2 снят В ФАЙЛЕ таблицы кусков.
Признак считается по вершинам и текстурам самого файла, не по списку opq863.bin и не кодом движка. python mkref_city.py IN.shr OUT.shr"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import census, city
b = bytearray(Path(sys.argv[1]).read_bytes()); topq = census.tex_opaque(bytes(b)); un, keep = city.plan(bytes(b), topq)
for (i, tr, off) in un:
    fl, = struct.unpack_from('<I', b, off); struct.pack_into('<I', b, off, fl & ~2)
Path(sys.argv[2]).write_bytes(bytes(b)); print('снят флаг 2 у %d кусков города (%d треугольников); оставлено «листов» моря: %d' % (len(un), sum(x[1] for x in un), len(keep)))
