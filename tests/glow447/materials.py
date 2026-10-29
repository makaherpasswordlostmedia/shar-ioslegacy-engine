"""Exercise the production mesh exporter: preserve authored BLMD=2 without changing other blend modes."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import psp_export as ex
ex.load_tex = lambda *a, **k: 0
ex.binary_alpha = lambda *a: True
raw = bytearray()
at = {}
for name, a in dict(position=np.eye(3, dtype='<f4'), uv=np.zeros((3, 2), '<f4'),
                    color=np.ones((3, 3), '<f4'), indices=np.arange(3, dtype='<u4')).items():
    at[name] = [len(raw), a.size]; raw.extend(a.tobytes())
for mode in (0, 1, 2, 3):
    meta = dict(objects=[dict(mesh='probe', matrix=np.eye(4).ravel().tolist())],
                meshes={'probe': [dict(attributes=at, shader='probe')]},
                materials={'probe': dict(alpha=False, blend=mode)})
    flags = ex.pack_prims(meta, raw, {}, [])[0][1]
    assert bool(flags & (1 << 24)) == (mode == 2), (mode, flags)
    if mode == 2: assert flags & 2
print('PASS: authored BLMD 0/1/2/3, additive only for 2')
