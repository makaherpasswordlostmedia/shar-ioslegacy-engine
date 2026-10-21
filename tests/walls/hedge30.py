#!/usr/bin/env python3
"""Five authored points ×30/60: measured <1km/h and no crossing, OLD real code"""
import csv,hashlib,json,os,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT);sys.path.insert(0,str(ROOT/'tools/twins'))
import walls_family as W
OBS=Path(os.environ.get('HEDGE_OBSERVER',str(ROOT.parent/'shar-psp-ps2-w')))
fact=OBS/'knowledge/facts/ps2-hedges-30-60.yaml';F=json.loads(fact.read_text())
OUT=ROOT/'build/hedge30';OUT.mkdir(exist_ok=True)
targets=json.loads((OBS/F['evidence']['source_targets']).read_text());target={r['name']:r for r in targets}
S=W.read_col(1)['seg'];inputs=[];sources={str(fact):hashlib.sha256(fact.read_bytes()).hexdigest()}
assert {r['point'] for r in F['table']}=={'J9_4','hedge000','hedge002','hedge004','fence_f008'} and len(F['table'])==10
for r in F['table']:
 assert r['last_speed_kmh']<1
 recipe=OBS/'tools/twins/recipes'/(r['id']+'_repeat.json');R=json.loads(recipe.read_text());launch=max(x['at'] for x in R['writes'] if x['name']=='car_vel[0]')
 path=OBS/'build/twins/o4'/r['id']/'trace.tsv';tr=list(csv.DictReader(path.open(),delimiter='\t'))
 initial=next(x for x in tr if int(x['rel'])==launch+2)
 M=np.asarray([float(initial[f'mat[{i}]']) for i in range(16)]).reshape(4,4)
 v=[float(initial[f'car_vel[{i}]']) for i in range(3)];cm=np.asarray([float(initial[f'car_cm[{i}]']) for i in range(3)])
 assert abs(np.linalg.norm(np.asarray(v)[[0,2]])*3.6-r['speed_2f_kmh'])<1e-5
 cm_local=(cm-M[3,:3])@np.linalg.inv(M[:3,:3])
 if r['point']=='J9_4':
  # Source nearest hedge line in tangent range; observer did not supply a primitive identity
  x,y,z=r['end'];choices=[]
  for i,s in enumerate(S):
   side,t,L=W.seg_side(S,i,x,-z)
   if s[6]<-1.5e6 and 0<t<L:choices.append((abs(side),i))
  dist,seg=min(choices);assert dist<3
 else:
  seg=target[r['point']]['source_seg'];assert np.max(abs(S[seg]-target[r['point']]['source_segment']))<1e-6
 pad=sorted(R['pad'],key=lambda x:x[0]);state=0;buttons=[]
 for f in range(launch+3,launch+301):
  for at,key,val in pad:
   if key=='cross' and at<=f:state=val
  buttons.append(int(state))
 inputs.append(r['id']+' 298 '+str(seg)+'\n'+' '.join(map(str,[*M.reshape(-1),*v,*cm_local]))+'\n'+' '.join(map(str,buttons))+'\n')
 for p in (path,recipe):sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'poses.txt').write_text(''.join(inputs));(OUT/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
def judge(log):
 rows=[l.split() for l in log.splitlines()];assert len(rows)==10 and {r[0] for r in rows}=={r['id'] for r in F['table']}
 result=[]
 for r in rows:
  speed,side,entry=map(float,r[4:]);ok=speed<1 and side>0
  print(('PASS' if ok else 'FAIL'),r[0],'endkmh',speed,'min_frontside_m',side,'entrykmh',entry);result.append(ok)
 return all(result)
states={}
for side,flags in [('new',[]),('old',['-DCOL_HEDGE_PASS_OLD=1']),('class-old',['-DCOL_HEDGE_CLASS_OLD=1'])]:
 exe=OUT/side;subprocess.run(['cc','-O2','-DSKIN_HOST','-Iviewer',*flags,'tests/walls/hedge30.c','viewer/col.c','-lm','-o',exe],check=True)
 log=subprocess.check_output([exe,ROOT/'build/level.shr',OUT/'poses.txt'],text=True);(OUT/(side+'.log')).write_text(log)
 states[side]=judge(log);print(side,states[side])
ok=states['new'] and not states['old'] and not states['class-old']
print('PASS' if ok else 'FAIL','five native points ×30/60, old pass-through/classification rejected')
raise SystemExit(not ok)
