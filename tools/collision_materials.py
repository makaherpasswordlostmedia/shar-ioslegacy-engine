#!/usr/bin/env python3
"""Update only reserved COL1 material fields; preserve textures, mesh/PVS and all offsets.

Rejects changed geometry rather than silently shipping a level with stale visibility data.
Use build_level.sh for any geometry change. This path avoids re-exporting visuals for a policy change.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import psp_export as ex
from p3d import read

ap=argparse.ArgumentParser()
ap.add_argument('--source',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--level',type=int,required=True,choices=range(1,8))
args=ap.parse_args()
src=args.source.read_bytes();assert src[:4]==b'SHR7','not SHR7'
art=ex.GAME/'art';level=args.level
names=[f'l{level}_terra']+sorted(p.stem for p in art.glob(f'l{level}r*.p3d'))+sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
tri,box,cyl,seg,rep=ex.col_collect([(n,read(art/(n+'.p3d'))) for n in names])
assert not rep['errors'],rep['errors']
sec,_=ex.col_section(tri,box,cyl,seg)
co=struct.unpack_from('<I',src,92)[0]
old=bytearray(src[co:co+len(sec)]);new=bytearray(sec)
slots=[48+len(tri)*48+i*64+60 for i in range(len(box))]
slots += [48+len(tri)*48+len(box)*64+i*48+36 for i in range(len(cyl))]
for off in slots:
    old[off:off+4]=new[off:off+4]=b'\0'*4
assert old==new,'COL1 geometry/grid differs: rebuild the level and PVS with original visual settings'
result=bytearray(src)
for off in slots:result[co+off:co+off+4]=sec[off:off+4]
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_bytes(result)
report=dict(level=level,source=str(args.source),out=str(args.out),bytes=len(result),
            source_sha256=hashlib.sha256(src).hexdigest(),out_sha256=hashlib.sha256(result).hexdigest(),
            foliage=rep['foliage'],changed_bytes=sum(a!=b for a,b in zip(src,result)),
            invariant='Only COL1 volume material fields changed; visuals, PVS, physics geometry, file size/offsets byte-identical')
args.out.with_suffix('.materials.json').write_text(json.dumps(report,indent=2))
print(f"PASS {len(rep['foliage'])} foliage volumes, {report['changed_bytes']} bytes changed; all geometry/textures/PVS preserved")
