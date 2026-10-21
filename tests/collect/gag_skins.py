#!/usr/bin/env python3
"""Disc mesh census vs embedded CHR1; paired headless pictures for every L1 skin gag.

Red controls: --plant absent removes the table; --plant pictures substitutes
the red image. Both must fail this same checker, not a separate expectation.
"""
import argparse, struct, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import char_export as ce
from p3d import read, string, walk
from convert import geometry

def faces(P):
    if len(P) < 3: return 0
    return int(np.count_nonzero(np.linalg.norm(np.cross(P[1:-1]-P[:-2], P[2:]-P[:-2]), axis=1) > 1e-8))

def check(pack, green, red, plant):
    b = pack.read_bytes(); ng, go = struct.unpack_from('<II', b, 44); ns, so = struct.unpack_from('<II', b, 56)
    if plant == 'absent': ns = 0
    total = shots = 0
    with tempfile.TemporaryDirectory() as td:
        for g in range(ng):
            name = b[go+128*g:go+128*g+16].split(b'\0')[0].decode()
            root = read(ce.GAME / 'art/nis/gags' / (name + '.p3d'))
            meshes = {string(c.data)[0]: c for c in root.children if c.id == 0x10001}
            if not meshes: continue
            expected = 0
            for comp in (c for c in root.children if c.id == 0x4512):
                for ref in walk(comp):
                    if ref.id != 0x4515: continue
                    for pg in meshes[string(ref.data)[0]].children:
                        if pg.id == 0x10002: expected += sum(len(p['indices'])//3 for p in geometry(pg)[1])
            got = models = 0
            for i in range(ns):
                off, size, idx = struct.unpack_from('<IIH', b, so+64*i)
                if idx != g: continue
                p = Path(td) / 'gag.chr'; p.write_bytes(b[off:off+size]); m = ce.read_chr(p)
                assert 0 < len(m['joints']) <= 64
                assert m['clips'] and len(m['clips'][0]['tracks']) == len(m['joints'])
                got += sum(faces(bt['pos']) for bt in m['batches']); models += 1
            assert models and got == expected, f'{name}: triangles {got}/{expected}, models {models}'
            if green:
                a = np.asarray(Image.open(green / f'gag{g}.png').convert('RGB'))
                r = np.asarray(Image.open(red / f'gag{g}.png').convert('RGB'))
                if plant == 'pictures': a = r
                # Radar is below/right; scene skins are centred by the scenario.
                changed = int(np.any(a[:210, :340] != r[:210, :340], axis=2).sum())
                assert changed, f'{name}: no skin pixels changed against OLD'
                shots += 1
                print(f'{name}: triangles {got}/{expected}, models {models}, pixels {changed}')
            total += 1
    print(f'PASS {pack.name}: {total} complete skins, {shots} paired screenshots')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('pack', type=Path)
    ap.add_argument('--green', type=Path); ap.add_argument('--red', type=Path)
    ap.add_argument('--plant', choices=['absent', 'pictures']); a = ap.parse_args()
    assert bool(a.green) == bool(a.red)
    check(a.pack, a.green, a.red, a.plant)
