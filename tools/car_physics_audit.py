#!/usr/bin/env python3
"""Inventory original car tuning and root physics without inferring runtime units.

Reads only the user's disc files. Matrix order is XX,XY,XZ,YY,YZ,ZZ:
https://docs.donutteam.com/docs/Pure3DFiles/DataStructure
The inertia density convention and PhysicsVector's game use remain unverified;
this inventory intentionally does not alter the simulation.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, string
from con2h import parse

GAME = ROOT / 'hit-and-run-web/source/game'


def physics(path):
    objects = []
    for obj in read(path).children:
        if obj.id != 0x7011000:
            continue
        name, p = string(obj.data)
        version, = struct.unpack_from('<I', obj.data, p)
        material, p = string(obj.data, p + 4)
        njoints, volume, sensitivity = struct.unpack_from('<Iff', obj.data, p)
        roots = []
        for joint in obj.children:
            if joint.id != 0x7011020:
                continue
            index, jvolume, stiffness, amax, amin, dof = struct.unpack_from('<I4fI', joint.data)
            if index:
                continue
            matrices = [list(struct.unpack('<6f', c.data)) for c in joint.children if c.id == 0x7011001]
            vectors = [list(struct.unpack('<3f', c.data)) for c in joint.children if c.id == 0x7011002]
            root = dict(index=index, volume=jvolume, stiffness=stiffness, max_angle=amax,
                        min_angle=amin, dof=dof, physics_vectors=vectors, inertia_matrices=matrices)
            if len(matrices) == 1:
                xx, xy, xz, yy, yz, zz = matrices[0]
                eig = np.linalg.eigvalsh([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
                root['eigenvalues'] = eig.tolist()
                root['positive_definite'] = bool(np.isfinite(eig).all() and (eig > 0).all())
            roots.append(root)
        objects.append(dict(name=name, version=version, material=material, joints=njoints,
                            volume=volume, resting_sensitivity=sensitivity, roots=roots))
    return objects


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    rows = []
    for con in sorted((GAME / 'scripts/cars').glob('*.con')):
        model = GAME / 'art/cars' / (con.stem + '.p3d')
        row = dict(name=con.stem, tuning=parse(con), con_sha256=hashlib.sha256(con.read_bytes()).hexdigest(),
                   model_present=model.is_file())
        if model.is_file():
            row['model_sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
            row['physics'] = physics(model)
        rows.append(row)
    roots = [root for row in rows for obj in row.get('physics', []) for root in obj['roots']]
    summary = dict(cars=len(rows), models=sum(r['model_present'] for r in rows), root_joints=len(roots),
                   inertia_matrices=sum(len(r['inertia_matrices']) for r in roots),
                   positive_definite=sum(r.get('positive_definite', False) for r in roots))
    report = dict(matrix_order=['XX', 'XY', 'XZ', 'YY', 'YZ', 'ZZ'],
                  format_source='https://docs.donutteam.com/docs/Pure3DFiles/DataStructure',
                  unresolved=['Inertia mass/density normalization', 'PhysicsVector game-space origin and COM use',
                              'Original suspension/contact solver behavior for each car'],
                  summary=summary, cars=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
