#!/usr/bin/env python3
"""Direct rigid prop PhysicsObject + its own ATC row; no vehicle-articulation guess"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
from p3d import read,walk,string
from interiors import leaves
from fx_export import atc_table
def body(path,name):
 root=read(path);ent=next(c for c in walk(root) if c.id==0x3f00002 and string(c.data)[0]==name)
 attr=next(c for c in ent.children if c.id==0x3000600);cls,atc=struct.unpack_from('<II',attr.data)
 row=atc_table()[atc];o=next(c for c in ent.children if c.id==0x7011000)
 _,p=string(o.data);_,p=string(o.data,p+4);kind,volume,root_rest=struct.unpack_from('<Iff',o.data,p)
 vectors=[c for c in o.children if c.id==0x7011002];matrices=[c for c in o.children if c.id==0x7011001]
 if len(vectors)!=1 or len(matrices)!=1 or volume<=0:raise ValueError('not a single rigid prop body')
 center=list(struct.unpack('<3f',vectors[0].data));tensor=list(struct.unpack('<6f',matrices[0].data))
 coll=next(c for c in ent.children if c.id==0x7010000)
 shapes=[s for v in coll.children if v.id==0x7010001 for s in leaves(v,name)]
 return dict(source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),entity=name,
             cls=cls,atc=atc,attribute=row,kind=kind,volume=volume,root_rest=root_rest,
             center_native=center,inertia_volume_native=tensor,
             inertia_density_scaled_native=[v*row['mass']/volume for v in tensor],
             density_note='authored ATC mass / volume; runtime activation must be checked separately',
             collision_reflected_Z=shapes)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('path',type=Path);ap.add_argument('entity');ap.add_argument('--out',type=Path);a=ap.parse_args()
 s=json.dumps(body(a.path.resolve(),a.entity),indent=2)+'\n'
 if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(s)
 else:print(s,end='')
if __name__=='__main__':main()
