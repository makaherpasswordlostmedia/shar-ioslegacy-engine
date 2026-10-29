#!/usr/bin/env python3
"""Actual framebuffer flame pixels captured WHILE a slow read is pending.
OLD must fail because there are no rendered frames during the blocked read.
"""
import argparse,json,re,sys
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'tools'))
import load_export as L
ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
log=(a.run/'smoke.txt').read_text();errors=[];proof=[]
if not re.search(r'^END$',log,re.M):errors.append('missing END')
summary=re.search(r'LOADFUSE385 frames=(\d+) images=(\d+) old=(\d+)',log)
if not summary or int(summary[1])<12 or int(summary[2])!=2:errors.append('no independent animation during slow read')
rows=[dict(re.findall(r'(\w+)=(\S+)',l)) for l in log.splitlines() if l.startswith('LOADFUSE385 image=')]
if len(rows)!=2:errors.append('need two actual pending-read framebuffer captures')
if rows:
 res=L.export('load',a.out/'reference-load.shr',mocks=False);fire=next(t for t in res['screens']['loading'] if t['name']=='Fire');phases=set()
 for row in rows:
  idx=int(row['image']);stride=int(row['stride']);fmt=int(row['format']);t=float(row['t']);prog=int(row['prog']);phase=L.clock_index(t,fire['rate'])%len(fire['bitmaps']);phases.add(phase)
  b=(a.run/f'rfsnap_fuse385_{idx}.bin').read_bytes();assert len(b)==int(row['bytes'])
  if fmt==0:
   v=np.frombuffer(b,dtype='<u2').reshape(272,stride)[:,:480].astype(np.uint32)
   rgb=np.stack([(v&31)*255//31,((v>>5)&63)*255//63,((v>>11)&31)*255//31],axis=2).astype(np.uint8)
  elif fmt==3:rgb=np.frombuffer(b,dtype=np.uint8).reshape(272,stride,4)[:,:480,:3]
  else:raise ValueError('unsupported framebuffer '+str(fmt))
  Image.fromarray(rgb).save(a.out/f'pending-{idx}.png')
  state=dict(PROGRESS=prog,T=t,LEVEL=int(row['level']),show={'ALWAYS'})
  wanted=np.asarray(L.mock(res,'loading',state).convert('RGB'),float)
  swap=dict(res,screens=dict(res['screens']));wrongfire=dict(fire,bitmaps=list(reversed(fire['bitmaps'])));swap['screens']['loading']=[wrongfire if x is fire else x for x in res['screens']['loading']]
  other=np.asarray(L.mock(swap,'loading',state).convert('RGB'),float)
  alpha=np.maximum(*(np.asarray(res['qbitmaps'][k])[...,3] for k in fire['bitmaps']))>100
  x,y,w,h=fire['dst'];x+=L.fuse_shift(fire,prog);actual=rgb[y:y+h,x:x+w].astype(float);want=wanted[y:y+h,x:x+w];wrong=other[y:y+h,x:x+w]
  mask=alpha&(np.abs(want-wrong).max(axis=2)>=20);assert mask.sum()>=5
  right=float(np.abs(actual-want)[mask].mean());bad=float(np.abs(actual-wrong)[mask].mean())
  proof.append(dict(phase=phase,time=t,progress=prog,pending=int(row['pending']),right_error=right,wrong_error=bad))
  if right>15 or bad<right+3 or row['pending']!='1':errors.append('flame pixels do not match moving native phase')
 if phases!={0,1}:errors.append('both native flame phases not seen')
for line in log.splitlines():
 if line.startswith('STAT '):
  p=line.split();s=dict(zip(p[2::2],p[3::2]))
  if any(float(s.get(k,0)) for k in ('readerr','memfail','allocfail','gebad','geskip','missvis')):errors.append('native error: '+line)
result=dict(status='FAIL' if errors else 'PASS',errors=errors,summary=summary.groups() if summary else None,captures=proof)
(a.out/'proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(bool(errors))
