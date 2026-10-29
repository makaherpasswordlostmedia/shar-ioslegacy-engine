#!/usr/bin/env python3
"""Native triangle-list hair survives CHR1 with its winding and animation.

The independent reference decodes the owner's VIF positions. Existing strip
models must retain every vertex attribute; a connected-strip mutation must fail.
"""
import argparse,contextlib,io,json,struct,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import char_export as ce
from p3d import read,walk,string
from vif import unpack
from npc_list import npcs

def face_key(t):
 v=[tuple(float(x) for x in p) for p in np.asarray(t,dtype=np.float32)]
 return min(tuple(v),tuple(v[1:]+v[:1]),tuple(v[2:]+v[:2]))
def faces(P):
 out=[]
 for i in range(len(P)-2):
  t=P[[i+1,i,i+2]] if i&1 else P[i:i+3]
  if np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))>1e-8:out.append(t)
 return out

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--plant',choices=['hairstrip','winding']);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 oldcode=subprocess.check_output(['git','show','219c959:tools/char_export.py'],text=True)
 old={'__name__':'old_char_export','__file__':str(ROOT/'tools/char_export.py')};exec(compile(oldcode,'old_char_export','exec'),old)
 if a.plant:
  original=ce.primitive_strips
  def mutated(strips,prim,shader):
   if prim==0 and a.plant=='hairstrip':return strips
   result=original(strips,prim,shader)
   if prim==0 and a.plant=='winding':
    result=[{k:v[[0,2,1]] for k,v in st.items()} for st in result]
   return result
  ce.primitive_strips=mutated
 root=read(ce.GAME/'art/chars/dolph_m.p3d');pg=next(c for c in walk(root) if c.id==0x10002 and string(c.data,4)[0]=='dolphhair_m')
 native=next(c for c in pg.children if c.id==0x10012);expected=[]
 for cmd,n,v,b,imm,data in unpack(native.data):
  if imm&0x3ff==4 and v==3 and b==32:
   P=np.frombuffer(data,'<f4',n*3).reshape(n,3).copy();P[:,2]*=-1;assert n%3==0;expected.extend(P.reshape(-1,3,3))
 assert len(expected)==94,'reference must include complete hair'
 out=a.out/'dolph.chr'
 with contextlib.redirect_stdout(io.StringIO()):ce.export('dolph','art/chars/dolph_m.p3d','art/chars/npd_a.p3d',out,keep=ce.npc_clip_names())
 model=ce.read_chr(out);hair=[bt for bt in model['batches'] if model['tex'][bt['tex']]['name']=='dolphhair.bmp'];actual=[t for bt in hair for t in faces(bt['pos'])]
 exact=sorted(map(face_key,actual))==sorted(map(face_key,expected))
 # Every original bind vertex has an actual bone influence summing to 128/128.
 assert hair and all(np.array_equal(bt['w'].sum(1),np.ones(len(bt['w']))) for bt in hair)
 wanted=ce.npc_clip_names();clips=[c['name'] for c in model['clips']]
 assert all(any(ce.clip_matches(c,w) for c in clips) for w in wanted)
 assert len(model['blink'])==7 and len(model['joints'])==33
 # New list support must leave existing strip-only NPCs byte-for-byte unchanged.
 paths=sorted({r['model'] for lv in range(1,8) for r in npcs(lv) if r['ok'] and r['name']!='dolph'});checked=0
 for path in paths:
  r=read(ce.GAME/path);before=old['load_strips'](r);after=ce.load_strips(r)
  assert len(before)==len(after)
  for (sh,A),(sh2,B) in zip(before,after):
   assert sh==sh2 and len(A)==len(B),(path,sh)
   for x,y in zip(A,B):
    assert x.keys()==y.keys() and all(np.array_equal(x[k],y[k]) for k in x),(path,sh)
  checked+=1
 try:old['load_strips'](root)
 except ValueError as err:old_reject=str(err)
 else:raise AssertionError('old exporter unexpectedly accepted complete Dolph')
 report=dict(ok=exact,reference_faces=len(expected),packed_faces=len(actual),strip_models_unchanged=checked,joints=33,clips=len(clips),blink_keys=7,size=out.stat().st_size,old_reject=old_reject,plant=a.plant)
 (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(('PASS' if exact else 'FAIL')+' '+json.dumps(report));return 0 if exact else 1
if __name__=='__main__':raise SystemExit(main())
