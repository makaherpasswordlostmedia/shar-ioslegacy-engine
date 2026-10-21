#!/usr/bin/env python3
"""Испорченные build/bootmarks.bin для красной части гейта правки 127 (tests/bootlogo/run.sh): каждый обязан упасть в
tools/bootmarks.py --verify / --check. crc пересчитывается, чтобы ловила именно проверка содержимого, а не crc.
  badmarks.py SRC OUTDIR -> OUTDIR/bad_magic.bin, bad_145.bin, bad_color.bin, bad_bpp.bin, bad_extra.bin"""
import struct, sys, zlib
from pathlib import Path
src, out = Path(sys.argv[1]), Path(sys.argv[2]); b = bytearray(src.read_bytes()); out.mkdir(parents=True, exist_ok=True)
def crc(x): x = bytearray(x[:-4]); return bytes(x + struct.pack('<I', zlib.crc32(x) & 0xFFFFFFFF))
def put(name, x): (out / name).write_bytes(x)
v = b[3] - ord('0'); rec0 = 20 + (0 if v == 3 else 4 * (16 if v == 2 else 4)); start = 20 if v == 3 else 12
m = bytearray(b); m[3] = ord('X'); put('bad_magic.bin', crc(m))                     # магия испорчена
m = bytearray(b); struct.pack_into('<H', m, start, 145); put('bad_145.bin', crc(m))       # знак 145 px шириной (шире слота)
m = bytearray(b)
if v == 3: struct.pack_into('<I', m, 12, 0xFF3050E0)                                    # общий фон BMK3
else: struct.pack_into('<I', m, start + 20 + (0 if v == 2 else 8), 0x003050E0 if v == 2 else 0xFF3050E0)
put('bad_color.bin', crc(m))                                                             # BMK2/3: фон не чёрный/прозрачный; BMK1: не серый
m = bytearray(b); m[start + 4] = 8; put('bad_bpp.bin', crc(m))                           # неверная глубина
# лишний знак без исходного файла (как баннер 124 из букв): копия первого знака с другим именем
n = struct.unpack_from('<H', b, 4)[0]; w, h = struct.unpack_from('<2H', b, start); packed = (w * h + 7) // 8 if v == 3 else (w * h + 1) // 2 if v == 2 else (w * h + 3) // 4
rec = bytes(b[start:start + rec0 + packed]); rec = rec[:6] + b'banner124'.ljust(14, b'\0') + rec[20:]
m = bytearray(b[:-4]) + rec + b'\0\0\0\0'; struct.pack_into('<H', m, 4, n + 1); put('bad_extra.bin', crc(m))
print('испорченные знаки ->', out)
