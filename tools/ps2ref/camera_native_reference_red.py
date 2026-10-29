#!/usr/bin/env python3
from pathlib import Path
import importlib.util,struct,json,hashlib
import argparse
parser=argparse.ArgumentParser(description='Offline negative controls for original true-camera references')
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--out',type=Path)
args=parser.parse_args();R=args.root.resolve();p=Path(__file__).resolve().parent/'camera_native_reference.py';spec=importlib.util.spec_from_file_location('cam',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
card=json.loads((R/'knowledge/facts/ps2-camera-after-landing.yaml').read_text());state=card['evidence']['snapshots'][0];path=R/state['path'];read=m.read_state;base=read(path,state['sha256']);ref=m.decode(base);u=lambda a:struct.unpack_from('<I',base,a)[0];f=lambda a:struct.unpack_from('<f',base,a)[0];cam=int(ref['camera'],16);active=int(ref['active'],16);sim=u(0x1295b50+0x4a8);results=[]
def check(tag,mutate,expected):
 dirty=bytearray(base);mutate(dirty)
 m.read_state=lambda q,h:bytes(dirty) if q==path else read(q,h)
 try:m.collect(R)
 except ValueError as e:
  if expected not in str(e):raise ValueError('Wrong failure for '+tag+': '+str(e))
  results.append(dict(control=tag,status='RED caught',reason=str(e)));print(tag,'RED',str(e),flush=True)
 else:raise ValueError('No rejection for '+tag)
 finally:m.read_state=read
check('registered_slot_pointer',lambda e:struct.pack_into('<I',e,0x609340+0x0c+4*u(0x609340+0x90),0),'registered slot')
check('eye_vs_inverse',lambda e:struct.pack_into('<f',e,cam+0xcc,f(cam+0xcc)+.01),'eye disagrees')
check('view_inverse_matrix',lambda e:struct.pack_into('<f',e,cam+0x88,f(cam+0x88)+.02),'not inverse')
check('native_frame_alignment',lambda e:struct.pack_into('<I',e,0x5167d8,u(0x5167d8)+1),'native-frame mismatch')
check('body_trace_alignment',lambda e:struct.pack_into('<f',e,sim+0x40,f(sim+0x40)+.03),'body alignment mismatch')
check('target_vs_matrix_ray',lambda e:struct.pack_into('<f',e,cam+0xdc,f(cam+0xdc)+1),'ray/matrix direction mismatch')
check('lens_vs_owner',lambda e:struct.pack_into('<f',e,cam+0x10,f(cam+0x10)+.01),'lens/owner mismatch')
def lens_planes(e):
 struct.pack_into('<f',e,cam+0x10,f(cam+0x10)+.01);struct.pack_into('<f',e,active+0x50,f(active+0x50)+.01)
check('lens_vs_independent_frustum',lens_planes,'lens/frustum mismatch')
try:read(path,'0'*64)
except ValueError as e:assert 'hash mismatch'in str(e);results.append(dict(control='wrong_snapshot_sha',status='RED caught',reason=str(e)))
else:raise ValueError('wrongSHA accepted')
old=m.sha;m.sha=lambda q:'0'*64 if q.name=='trace.tsv' else old(q)
try:m.collect(R)
except ValueError as e:assert 'trace hash mismatch'in str(e);results.append(dict(control='wrong_trace_sha',status='RED caught',reason=str(e)))
else:raise ValueError('wrongtraceSHA accepted')
finally:m.sha=old
report=dict(status='PASS',controls=results,source_state=state,mutations='Offline bytearray copies only, original EE/trace/card files unchanged',decoder_sha256=hashlib.sha256(p.read_bytes()).hexdigest());q=args.out
if q:
 q.parent.mkdir(parents=True,exist_ok=True);tmp=q.with_suffix(q.suffix+'.tmp');tmp.write_text(json.dumps(report,indent=1)+'\n');tmp.replace(q)
print('ALL',len(results),'negative controls caught')
