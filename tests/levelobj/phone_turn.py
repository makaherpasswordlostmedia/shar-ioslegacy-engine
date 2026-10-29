#!/usr/bin/env python3
"""Check the actual exported receiver: two continuous turns in its native 121-frame clip.

The disc's rotation keys at 0/29/40/70/99/100/120 encode 0/174/240/420/594/600/720 degrees.
The old shortest-arc tie reversed frames 40..70, leaving only one turn.
"""
import struct
import sys
from pathlib import Path
import numpy as np

def check(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'MSA2', 'not MSA2'
    n, table = struct.unpack_from('<2I', b, 4)
    for i in range(n):
        row = table + i * 96
        if b[row:row+80].split(b'\0',1)[0] != b'art/cards.p3d': continue
        off, size = struct.unpack_from('<2I', b, row+80)
        entry = b[off:off+size]
        _, ndraw, _, _, draws, _ = struct.unpack_from('<6I', entry)
        for j in range(ndraw):
            d = draws + 64*j
            if entry[d:d+32].split(b'\0',1)[0] != b'phone_icon': continue
            _, _, nm, mesh, nj, nf, fps, poses = struct.unpack_from('<6IfI', entry, d+32)
            assert nf == 121 and fps == 30 and nm > 0
            joint = struct.unpack_from('<I',entry,mesh+4)[0] >> 16
            a = np.frombuffer(entry,'<f4',nf*nj*12,poses).reshape(nf,nj,12)
            r = a[:,joint,:9].reshape(nf,3,3).transpose(0,2,1)
            relative = r @ r[0].T
            yaw = np.rad2deg(np.unwrap(np.arctan2(relative[:,0,2],relative[:,2,2])))
            expected = np.arange(nf)*6.0
            error = float(np.max(np.abs(yaw-expected)))
            assert error < .02, f'receiver reverses: total={yaw[-1]:.2f}, error={error:.2f}deg'
            assert np.diff(yaw).min() > 5.99
            print(f'PASS {path}: receiver 720deg, 120 forward steps; max error {error:.5f}deg')
            return
    raise AssertionError('missing native receiver')

if __name__ == '__main__':
    try: check(sys.argv[1])
    except (AssertionError,IndexError) as e: print('FAIL:',e);sys.exit(1)
