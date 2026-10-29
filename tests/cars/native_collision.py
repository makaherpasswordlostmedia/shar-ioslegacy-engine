#!/usr/bin/env python3
"""Verify original collision leaves against the owner's saved PS2 RAM.

This observer is scoped to the known L1 famil_v SimState in existing snapshots.
It follows the actual CollisionObject pointer and nine articulated joint poses;
it does not infer contact forces or material coefficient meanings.
--control bv and closed must reject the wrong source and a frozen rest pose.
Use system python3 (3.14+) for the PCSX2 ZIP Zstandard snapshots.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'hit-and-run-web/tools')]
from p3d import read, string
from interiors import leaves
from car_dump import skeleton


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--control', choices=['bv','closed'])
    args = ap.parse_args()
    try:
        with zipfile.ZipFile(args.state) as archive:
            ram = archive.read('eeMemory.bin')
    except NotImplementedError:
        raise SystemExit('PS2 snapshot uses ZIP Zstandard; run with system python3 3.14+, not the 3.11 venv')
    if len(ram)!=32*1024*1024:
        raise ValueError('not the expected PS2 EE memory image')

    def u(at):
        return struct.unpack_from('<I', ram, at)[0]

    def floats(at, count):
        return np.array(struct.unpack_from('<'+str(count)+'f', ram, at), dtype=np.float64)

    def pointer(at):
        p = u(at)
        if not (0x100000<=p<len(ram)-256 and p%4==0):
            raise ValueError(f'invalid RAM pointer at {at:x}: {p:x}')
        return p

    state = 0xa21860
    collision = pointer(state+0x74)
    vtable = pointer(collision)
    if b'Q23sim15CollisionObject\0' not in ram[vtable:vtable+256]:
        raise ValueError('SimState collision pointer lacks CollisionObject RTTI')
    if pointer(collision+0x18)!=state:
        raise ValueError('CollisionObject does not refer back to the observed SimState')
    parent = pointer(collision+0x20)
    if u(parent+0x24)!=5:
        raise ValueError('expected composite collision-volume parent')
    children = pointer(parent+0x34)
    count = u(children+4)
    array = pointer(children+12)
    if count!=9:
        raise ValueError('the observed collision object is not the complete famil_v shape tree')
    model = floats(state+16,16).reshape(4,4)
    pose = pointer(state+0xa8)
    bones = pointer(pose)
    source = ROOT/'hit-and-run-web/source/game/art/cars/famil_v.p3d'
    root = read(source)
    name = 'famil_vBV' if args.control=='bv' else 'famil_v'
    obj = next(c for c in root.children if c.id==0x7010000 and string(c.data)[0]==name)
    comp = next(c for c in root.children if c.id==0x4512)
    _,p = string(comp.data)
    skeleton_name,_ = string(comp.data,p)
    joints = skeleton(next(c for c in root.children if c.id==0x4500 and string(c.data)[0]==skeleton_name))
    by_owner = {}

    def visit(volume):
        joint,owner,n = struct.unpack('<IiI',volume.data)
        kids = [c for c in volume.children if c.id==0x7010001]
        if n!=len(kids): raise ValueError('invalid authored volume child count')
        if kids:
            for child in kids: visit(child)
        else:
            # A different authored tree can have repeated owners. Preserve that
            # ambiguity so a wrong-tree control fails the comparison itself,
            # rather than being mistaken for a rejected fixture/parser error.
            by_owner.setdefault(owner, []).append((joint,next(leaves(volume,name))))

    for child in obj.children:
        if child.id==0x7010001: visit(child)
    rows,failures = [],0
    for i in range(count):
        native = pointer(array+4*i)
        kind,joint,owner = struct.unpack_from('<3I',ram,native+0x24)
        row = dict(pointer=hex(native), joint=joint, owner=owner, native_kind=kind)
        if owner not in by_owner:
            row.update(passed=False, reason='missing authored owner')
            failures+=1; rows.append(row);continue
        if len(by_owner[owner])!=1:
            row.update(passed=False, reason='ambiguous authored owner',
                       authored_candidates=len(by_owner[owner]))
            failures+=1; rows.append(row);continue
        source_joint,leaf = by_owner[owner][0]
        expected_kind = dict(box=3,sphere=1)[leaf['kind']]
        # The original palette is 27 records of 192 bytes; each current world
        # matrix starts at +104. It includes actual suspension/hinge motion.
        W = floats(bones+joint*192+104,16).reshape(4,4)
        if args.control=='closed': W = joints[source_joint][3]@model
        if not np.allclose(W[:,3],[0,0,0,1],atol=1e-6,rtol=0):
            raise ValueError('invalid native joint matrix')
        local = np.array(leaf['center'])*[1,1,-1]
        expected = (np.r_[local,1]@W)[:3]
        actual = floats(native+8,3)
        # Floating dot products and translations are performed in f32 on PS2.
        # Bound their rounding by operand magnitude, not a calibrated distance.
        budget = 8*np.finfo(np.float32).eps*(abs(W[3,:3])+abs(local)@abs(W[:3,:3])+1)
        center_ok = bool((abs(actual-expected)<=budget).all())
        if leaf['kind']=='box':
            A = np.array(leaf['axes'])*[1,1,-1]
            expected_axes = A@W[:3,:3]
            actual_axes = floats(native+0x4c,9).reshape(3,3)
            h = np.array(leaf['halfExtents'])
            actual_half = floats(native+0x70,3)
            shape_ok = bool(np.allclose(expected_axes,actual_axes,atol=2e-6,rtol=0) and np.array_equal(h,actual_half))
            row.update(max_axis_error=float(abs(expected_axes-actual_axes).max()),half=actual_half.tolist())
        else:
            radius = floats(native+0x4c,1)[0]
            shape_ok = radius==leaf['radius']
            row.update(radius=float(radius))
        ok = kind==expected_kind and joint==source_joint and center_ok and shape_ok
        row.update(passed=bool(ok),joint_name=joints[source_joint][0],kind=leaf['kind'],
                   center=actual.tolist(),expected_center=expected.tolist(),
                   center_error_m=float(np.linalg.norm(actual-expected)),rounding_bound=budget.tolist())
        rows.append(row);failures+=not ok
    report = dict(passed=not failures, failures=int(failures), rows=rows, control=args.control,
                  observed_collision_object=hex(collision), source_object=name,
                  authored_leaf_count=sum(map(len,by_owner.values())),
                  ambiguous_authored_owners=[owner for owner,items in by_owner.items() if len(items)>1],
                  state_sha256=hashlib.sha256(args.state.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  scope='L1 famil_v shape selection and articulated geometry; contact solver and material coefficients remain unverified')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f"{'PASS' if not failures else 'FAIL'} native collision leaves={count} failures={failures} control={args.control}")
    return int(bool(failures))


if __name__=='__main__':
    raise SystemExit(main())
