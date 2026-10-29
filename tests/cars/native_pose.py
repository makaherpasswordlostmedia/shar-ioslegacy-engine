#!/usr/bin/env python3
"""Original model/COM rest binding, without deriving an expected result from C."""
import struct,sys
from pathlib import Path
import numpy as np
v=Path(sys.argv[1]).read_text().split();assert v[0]=='famil_v',v
actual=np.array(list(map(float,v[-3:])))
b=Path(sys.argv[2]).read_bytes();M=np.array(struct.unpack_from('<16f',b,0xa21870)).reshape(4,4)
cm=np.array(struct.unpack_from('<3f',b,0x1298884));observed=(cm-M[3,:3])@np.linalg.inv(M[:3,:3]);observed[0]*=-1
error=np.max(np.abs(actual-observed))
# Authored closed parts and runtime articulation differ by up to 0.15 mm in this
# saved resting pose. The previous unbound centre misses it by centimetres.
assert error<.00015,(actual,observed,error)
assert abs(float(v[2])-.38028517)<1e-6,'legacy radius proxy survived CAR1'
print(f'PASS original resting model/COM binding: max error {error*1000:.4f} mm; authored wheel radius preserved through CAR1')
