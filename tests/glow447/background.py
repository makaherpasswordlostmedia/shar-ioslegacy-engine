"""Create a background-only reference for the fixed L7 field camera (test data only).
Usage: background.py SOURCE.shr DEST.shr
Only the five authored glow64 city records are hidden; no production rule uses IDs.
"""
from pathlib import Path
import struct
import sys
src, dst = map(Path, sys.argv[1:])
assert src.resolve() != dst.resolve(), 'reference requires a separate copy'
b = bytearray(src.read_bytes())
n = struct.unpack_from('<I', b, 8)[0]
off = struct.unpack_from('<I', b, 76)[0]
count = 0
for i in range(n):
    r = off + 80*i
    tex, flags, nv, ni, owner = struct.unpack_from('<5i', b, r+24)
    if tex != 78 or owner != 0: continue
    bounds = struct.unpack_from('<6f', b, r)
    assert -150 < bounds[0] < -100 and 580 < bounds[2] < 625, bounds
    struct.pack_into('<i', b, r+36, 0)
    count += 1
assert count == 5, count
dst.write_bytes(b)
print('Background reference: five field glow pieces hidden')
