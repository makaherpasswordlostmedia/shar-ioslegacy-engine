#!/usr/bin/env python3
"""Native lamp axis and mode migration through actual spBillQuad; --red loses axis.

Meshes are omitted: source billboard modes, poses, dimensions and instances remain native.
This is a geometry check, not a GPU or PSP acceptance claim.
"""
import ctypes
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import prp2_export as P

out = ROOT / 'build/codex-terminal/rob-pack/371'
out.mkdir(parents=True, exist_ok=True)
lib = out / 'axis.so'
subprocess.run(['cc', '-shared', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'),
                str(ROOT / 'tests/billboards/axis.c'),
                *(str(ROOT / 'viewer' / (n + '.c')) for n in ('stateprops', 'props', 'col', 'car', 'coins')),
                '-lm', '-o', str(lib)], check=True)
dll = ctypes.CDLL(str(lib))
f = dll.axisQuad
ptr = ctypes.POINTER(ctypes.c_float)
f.argtypes = [ctypes.c_int, ptr, ptr, ptr, ptr, ctypes.c_float, ctypes.c_float, ptr]
f.restype = ctypes.c_int
mode_counts = dll.axisModes
mode_counts.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
mode_counts.restype = ctypes.c_int
red = '--red' in sys.argv
checks = bad = constrained = 0


def arr(x):
    return np.ascontiguousarray(x, dtype=np.float32)


def call(mode, joint, world, pos, eye, width, height):
    inputs = [arr(x) for x in (joint, world, pos, eye)]
    vertices = np.empty(12, np.float32)
    ok = f(mode, *(x.ctypes.data_as(ptr) for x in inputs), width, height, vertices.ctypes.data_as(ptr))
    if not ok or not np.isfinite(vertices).all():
        raise ValueError('No finite native quad')
    return vertices.reshape(4, 3)


for level in range(1, 8):
    sp = P.StateProps(level, P.ROOT / 'hit-and-run-web/source/game/art', lambda f, m: [], lambda f, s: 0, verbose=False)
    modes = [b['mode'] for t in sp.types for b in t['bills']]
    section = sp.section({0: 0})
    buffer = ctypes.create_string_buffer(section)
    counts = (ctypes.c_uint * 4)()
    err = mode_counts(buffer, len(section), counts)
    if err or list(counts) != [modes.count(m) for m in range(4)]:
        raise ValueError(f'Native SPR1 mode serialization failed: level{level} err{err}')
    print('level', level, 'modes', {m: modes.count(m) for m in sorted(set(modes))})
    for t in sp.types:
        for b in t['bills']:
            J = t['JW'][b['joint']]
            packed = np.concatenate([J[:3, :3].flatten(order='F'), J[:3, 3]])
            # First authored instance; other camera elevations exercise the same native axis.
            R = t['inst'][0][0][:3, :3].T if t['inst'] else np.eye(3)
            W = R.flatten(order='F')
            centre = R @ (J[:3, :3] @ b['t'] + J[:3, 3])
            for elevation in (-20., 0., 20.):
                eye = centre + [12., elevation, 16.]
                mode = 1 if red and b['mode'] in (2, 3) else b['mode']
                v = call(mode, packed, W, b['t'], eye, b['w'], b['h'])
                y = (v[2] - v[0]) / b['h']
                expected = np.array([0., 1., 0.]) if b['mode'] == 2 else R @ J[:3, 1]
                if b['mode'] in (0, 2, 3):
                    expected /= np.linalg.norm(expected)
                    err = np.linalg.norm(y - expected)
                    checks += 1
                    if err > 1e-4:
                        bad += 1
                        print('FAIL', level, t['name'], b['name'], 'up_error', float(err))
                if b['mode'] in (2, 3):
                    constrained += 1
            if b['mode'] in (2, 3):
                # Looking exactly along the constrained axis must stay finite.
                axis = np.array([0., 1., 0.]) if b['mode'] == 2 else R @ J[:3, 1]
                call(b['mode'], packed, W, b['t'], centre + axis * 10., b['w'], b['h'])
if constrained < 30:
    raise ValueError('Native lamps not covered')
print('checks', checks, 'constrained', constrained, 'failures', bad)
raise SystemExit(bool(bad))
