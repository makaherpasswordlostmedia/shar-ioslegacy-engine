#!/usr/bin/env python3
"""Real packed city vertices + retained CAMF; lost-risk and unaccelerated OLD controls"""
import argparse,hashlib,json,math,re,struct,subprocess,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];O=R/'build/perf6-source';O.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--stage',type=Path,default=R/'build/ship_stage');args=ap.parse_args()
sys.path.insert(0,str(R/'tests/guard340'));import ge340 as G
level=args.stage/'level.shr';blob=level.read_bytes();npc=struct.unpack_from('<I',blob,8)[0];pt=struct.unpack_from('<I',blob,76)[0];nc,ct=struct.unpack_from('<II',blob,80)
cells=[struct.unpack_from('<6fIIIII',blob,ct+48*i) for i in range(nc)]
run=args.run;poses=G.camf_poses(run/'smoke.txt');assert poses
records=[];covered=set()
for name,eye,at,fov,near in poses:
 basis=np.array(G.basis(eye,at),dtype=np.float32);tv=math.tan(math.radians(fov)/2)
 for i in range(npc):
  row=struct.unpack_from('<6fiIIII3ffIII2I',blob,pt+i*80);tex,fl,nv,n,owner=row[6:11];ox,oy,oz,sc=row[11:15];off,nf,ci=row[15:18]
  if owner or not fl&16 or not n or n>65535:continue
  bb=np.array(row[:6]).reshape(2,3);dist=np.maximum(np.maximum(bb[0]-eye,eye-bb[1]),0)
  if np.linalg.norm(dist)>60:continue
  stride=12 if fl&32 else 16;po=6 if stride==12 else 8
  matrix=(basis*np.float32(sc)).ravel();bias=basis@(np.array([ox,oy,oz],dtype=np.float32)-eye.astype(np.float32))
  head=struct.pack('<15f3I',*matrix,*bias,tv*16/9,tv,near,n,stride,po)
  start=cells[ci][9]+off;raw=blob[start:start+n*stride];assert len(raw)==n*stride
  records.append(head+raw);covered.add(i)
data=struct.pack('<I',len(records))+b''.join(records);p=O/'input.bin';p.write_bytes(data)
out={}
for name,flags in [('new',[]),('old',['-DGG_BATCH_OLD=1']),('shrink',['-DGG_BATCH_TEST_SHRINK=1'])]:
 exe=O/name;subprocess.run(['cc','-O2','-std=c11','-ffp-contract=off','-I',str(R/'viewer'),*flags,str(R/'tests/perf6/batch_host.c'),'-lm','-o',str(exe)],check=True)
 x=subprocess.run([exe,p],capture_output=True,text=True);(O/(name+'.log')).write_text(x.stdout+x.stderr);print(name,x.returncode,x.stdout.strip());out[name]={'rc':x.returncode,'metrics':x.stdout}
 assert (x.returncode==0)==(name=='new')
manifest={'records':len(records),'camera_poses':len(poses),'pieces':len(covered),'level_sha256':hashlib.sha256(blob).hexdigest(),'source_smoke_sha256':hashlib.sha256((run/'smoke.txt').read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(data).hexdigest(),'results':out}
(O/'proof.json').write_text(json.dumps(manifest,indent=2)+'\n');print('PASS real city/CAMF risk equivalence; OLD/no speed and shrunken-box controls RED')
