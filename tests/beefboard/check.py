#!/usr/bin/env python3
"""357/429: source-driven collision frame, on both actual scene exports and SHR7 packs.
No level rebuild: compare the three leaves and prove other bytes are unchanged.
SHR_ANIMCOL_FRAME_OLD=1 is the old-export negative control.
"""
import argparse, hashlib, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'hit-and-run-web/tools')]
import psp_export as P
from p3d import read, string
from car_dump import skeleton

def boxes(path):
    b = path.read_bytes(); co = struct.unpack_from('<I', b, 92)[0]
    if b[co:co+4] != b'COL1': raise ValueError(f'{path}: missing COL1')
    nt, nb = struct.unpack_from('<II', b, co+24)
    off = co+48+nt*48
    return b, off, np.frombuffer(b, '<f4', nb*16, off).reshape(-1,16)

def contains(a, row):
    # Exactly the float32 records written to COL1; no gameplay tolerance.
    return np.any(np.all(a.astype('<f4') == np.asarray(row, dtype='<f4'), axis=1))

a=argparse.ArgumentParser(); a.add_argument('--packs', type=Path, required=True)
a.add_argument('--old-packs', type=Path, required=True); args=a.parse_args()
ok=True
for level in (3,6):
    scene=f'l{level}r5'; name=scene+'_beefboard'
    root=read(P.GAME/'art'/f'{scene}.p3d')
    terra=read(P.GAME/'art'/f'l{level}_terra.p3d')
    ent=next(c for c in root.children if c.id==0x7010000 and string(c.data)[0]==name)
    sk=next(c for c in root.children if c.id==0x4500 and string(c.data)[0]==name)
    leaves=[]
    for c in ent.children:
        if c.id==0x7010001: leaves.extend(P.col_leaves(c,name))
    assert len(leaves)==3 and all(s['kind']=='box' for s in leaves)
    matrix=P.MIRROR@skeleton(sk)[0][3]@P.MIRROR
    expected=np.array([P.col_place(s,matrix)[1] for s in leaves],dtype='<f4')
    stale=np.array([P.col_place(s,np.eye(4))[1] for s in leaves],dtype='<f4')
    _, exported, _, _, _=P.col_collect([(f'l{level}_terra',terra),(scene,root)])
    source=all(contains(exported,row) for row in expected) and not any(contains(exported,row) for row in stale)
    newpath=args.packs/f'l{level}/level.shr'; oldpath=args.old_packs/f'l{level}_old.shr'
    new, off, bx=boxes(newpath); old, oldoff, ob=boxes(oldpath)
    if bx.shape!=ob.shape or off!=oldoff: raise ValueError('primitive layout changed')
    ids=np.flatnonzero(np.any(bx!=ob,axis=1))
    assets=len(ids)==3 and all(contains(bx,row) for row in expected) and all(contains(ob,row) for row in stale)
    # Moving a box changes its cell references and the COL1/JMP1 byte offsets.
    # Compare geometry byte-for-byte and each cell with only the three moved refs removed.
    def geometry_and_grid(data):
        co=struct.unpack_from('<I',data,92)[0]
        _,_,_,w,h,nt,nb,nc,ns,nr,jmp=struct.unpack_from('<3f8I',data,co+4)
        end=co+48+nt*48+nb*64+nc*48+ns*32
        start=np.frombuffer(data,'<u4',w*h+1,end)
        refs=np.frombuffer(data,'<u4',nr,end+4*(w*h+1))
        remove={(1<<29)|int(i) for i in ids}
        grid=[tuple(int(v) for v in refs[start[k]:start[k+1]] if int(v) not in remove) for k in range(w*h)]
        geom=bytearray(data[co+48:end])
        for i in ids: geom[nt*48+64*i:nt*48+64*(i+1)]=bytes(64)
        po=struct.unpack_from('<I',data,96)[0]
        # Original jump section lies between COL1's jmp offset and PRP1.
        jump=data[co+jmp:po].rstrip(bytes(1))
        return bytes(geom),grid,jump
    gn,cn,jn=geometry_and_grid(new); go,co,jo=geometry_and_grid(old)
    pn=struct.unpack_from('<I',new,96)[0]; po=struct.unpack_from('<I',old,96)[0]
    newco=struct.unpack_from('<I',new,92)[0]; oldco=struct.unpack_from('<I',old,92)[0]
    assets &= gn==go and cn==co and jn==jo and new[104:newco]==old[104:oldco]
    tail=bytearray(new[pn:]); oldtail=old[po:]
    # REGF footer stores an absolute offset, so relocation must be exactly the section delta.
    nf=tail.rfind(b'REGF'); of=oldtail.rfind(b'REGF')
    if nf != of or nf < 0: raise ValueError('REGF layout changed')
    nr=struct.unpack_from('<I',tail,nf+4)[0]; ore=struct.unpack_from('<I',oldtail,of+4)[0]
    assets &= nr-ore==pn-po
    struct.pack_into('<I',tail,nf+4,ore)
    assets &= bytes(tail)==oldtail
    print('  invariants geometry',gn==go,'grid',cn==co,'jump',jn==jo,'tail',bytes(tail)==oldtail)
    center=np.mean(expected[:,:3],axis=0); anchor=matrix[3,:3]
    print(f'L{level}: source={source} assets={assets} changed_boxes={ids.tolist()} root_port={anchor.tolist()}')
    print(f'  sha256={hashlib.sha256(new).hexdigest()} old={hashlib.sha256(old).hexdigest()}')
    ok &= source and assets
print('PASS beefboard357/429' if ok else 'FAIL beefboard357/429')
raise SystemExit(0 if ok else 1)
