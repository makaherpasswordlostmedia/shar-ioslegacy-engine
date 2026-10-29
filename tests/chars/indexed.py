#!/usr/bin/env python3
"""Lossless packed-strip contract, actual loader, memory and rendered poses.

The byte reconstruction below deliberately does not use the exporter's reader.
CHAR_INDEXED_OLD disables compression and must fail the strict memory contract.
"""
import contextlib,hashlib,io,json,os,struct,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import char_export as ce
OUT=ROOT/'build/char-indexed';OUT.mkdir(parents=True,exist_ok=True)
def load(p):return subprocess.run([str(OUT/'loader'),str(p)],capture_output=True,text=True)
def equal(a,b):
 if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
 if isinstance(a,(tuple,list)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 if isinstance(a,np.ndarray):return np.array_equal(a,b)
 return a==b
def reconstruct(b):
 nb,ob=struct.unpack_from('<I',b,16)[0],struct.unpack_from('<I',b,36)[0]
 result=[];indexed=[]
 for i in range(nb):
  o=ob+48*i;vt,prim,n,ov=struct.unpack_from('<4I',b,o);stride,flags,oi,stored=struct.unpack_from('<4I',b,o+28)
  if flags&4:
   assert vt&(3<<11)==2<<11
   ids=struct.unpack_from('<'+str(n)+'H',b,oi);assert max(ids)<stored
   data=b''.join(b[ov+j*stride:ov+(j+1)*stride] for j in ids);indexed.append((o,oi,stored))
  else:data=b[ov:ov+n*stride]
  result.append((vt&~(3<<11),prim,n,b[o+16:o+28],stride,flags&~4,data))
 return result,indexed
def main():
 subprocess.run(['cc','-std=c11','-O2','-DSKIN_HOST','-Iviewer','tests/chars/indexed_load.c','viewer/skin.c','-lm','-o',str(OUT/'loader')],cwd=ROOT,check=True)
 rows=[];allok=True
 for char in ('homer','bart','lisa','apu','marge'):
  new,old=OUT/(char+'.shr'),OUT/(char+'-old.shr')
  for p,legacy in ((old,True),(new,False)):
   env=os.environ.copy()
   if legacy:env['CHAR_INDEXED_OLD']='1'
   with (OUT/(p.stem+'.txt')).open('w') as f:subprocess.run([str(ROOT/'.venv/bin/python'),'tools/homer_export.py','--char',char,'--out',str(p)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
  A,B=old.read_bytes(),new.read_bytes();ra,_=reconstruct(A);rb,idx=reconstruct(B)
  assert ra==rb,(char,'packed strip differs')
  assert load(new).returncode==load(old).returncode==0
  # Python reader expands indices; all non-vertex assets and all attributes must match.
  ma,mb=ce.read_chr(old),ce.read_chr(new)
  for batch in mb['batches']:batch['flags']&=~4
  assert equal(ma,mb),(char,'skeleton/keys/texture/blink/attributes differ')
  poses=[]
  for suffix,t in [('loco_idle_rest',0.5),('loco_run',0.23),('kick',0.12)]:
   c=next((i for i,x in enumerate(ma['clips']) if x['name'].endswith('_'+suffix)),None)
   assert c is not None,(char,suffix)
   images=[]
   for m in (ma,mb):
    pal,_=ce.palette(m,ce.sample_local(m,c,t));sk=ce.skin(m,pal)
    images.append(ce.render(m,sk,[3,1.5,5],[0,1,0],size=(240,272)))
   assert np.array_equal(*images),(char,suffix,'pixels differ')
   assert np.any(images[0]!=images[0][0,0]),'empty render'
   Image.fromarray(images[1]).save(OUT/(char+'-'+suffix+'.png'));poses.append(suffix)
  if idx:
   _,oi,stored=idx[0];bad=bytearray(B);struct.pack_into('<H',bad,oi,stored)
   bp=OUT/(char+'-bad.shr');bp.write_bytes(bad)
   assert load(bp).returncode==1,'out-of-bounds index accepted'
  reduced=len(B)<len(A);allok&=reduced
  row=dict(char=char,old_bytes=len(A),new_bytes=len(B),saved_bytes=len(A)-len(B),percent=round((len(A)-len(B))/len(A)*100,2),indexed_batches=len(idx),poses=poses,vertices_exact=True,new_sha256=hashlib.sha256(B).hexdigest(),memory_pass=reduced)
  rows.append(row);print(('PASS' if reduced else 'FAIL')+' '+json.dumps(row),flush=True)
 report=dict(ok=allok,rows=rows,saved_bytes=sum(r['saved_bytes'] for r in rows),negative=os.environ.get('CHAR_INDEXED_OLD')=='1')
 (OUT/('old-result.json' if report['negative'] else 'result.json')).write_text(json.dumps(report,indent=2)+'\n');return 0 if allok else 1
if __name__=='__main__':raise SystemExit(main())
