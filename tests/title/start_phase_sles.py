#!/usr/bin/env python3
"""Bounded read-only SLES helper inspection, not proof of a PressStart binding/init phase."""
import hashlib, json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
p = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'hit-and-run-web/source/disc/SLES_518.97'
b = p.read_bytes(); assert b[:6] == b'\x7fELF\x01\x01', 'expected little-endian ELF32'
e = struct.unpack_from('<16sHHIIIIIHHHHHH',b); segments = []
for i in range(e[10]):
    r = struct.unpack_from('<8I',b,e[5]+e[9]*i)
    if r[0] == 1: segments.append((r[1],r[2],r[4]))
def word(addr):
    for off,va,size in segments:
        if va<=addr<va+size: return struct.unpack_from('<I',b,off+addr-va)[0]
    raise ValueError('unmapped address '+hex(addr))
# Actual helper subtracts input phase f16; generic colour wrapper passes f14 into f16.
assert word(0x1e7ba8) == 0x46106301, 'sub.s f12,f12,f16 changed'
assert word(0x1e7c5c) == 0x46007406, 'mov.s f16,f14 changed'
target=0x1e7b58;calls=[]
for off,va,size in segments:
    for j in range(0,size-3,4):
        if struct.unpack_from('<I',b,off+j)[0] == (0x0c000000|(target>>2)):calls.append(hex(va+j))
print(json.dumps(dict(sha256=hashlib.sha256(b).hexdigest(),pulse_helper=hex(target),phase_input='$f16',
                     direct_calls=calls,scope='PressStart Scrooby field/init binding NOT_ESTABLISHED; use documented PORT_RULE'),indent=2))
