#!/usr/bin/env python3
"""Available f01–f20 controlled protocols, frozen sources; diagnostic only

Default returns physical comparison status. --audit checks reproducibility,
source completeness of the AVAILABLE recordings and catches a wrong COM seed
"""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--evidence',type=Path,default=ROOT.parent/'shar-psp');ap.add_argument('--audit',action='store_true');a=ap.parse_args()
out=ROOT/'build/drop-family';out.mkdir(exist_ok=True)
seed=a.evidence/'build/codex-terminal/rob-rest/388/attempt8/original-drop/trace.json'
start=json.loads(seed.read_text())[0]
iv=np.array([[start['local'+str(i)] for i in (27,28,29)],[start['local'+str(i)] for i in (28,30,31)],[start['local'+str(i)] for i in (29,31,32)]])
angular=(iv@np.array([start['local'+str(i)] for i in (6,7,8)])).tolist()
values=[start['pm'+str(i)] for i in range(16)]+[start['vx'],start['vy'],start['vz']]+angular+[start['local'+str(i)]+start['local'+str(i+3)] for i in range(3)]+[start['local'+str(i)] for i in range(13,19)]
native0=np.array([start[k] for k in ('x','y','z','cx','cy','cz')]);native0[[2,5]]*=-1
def poseok(text):
 try:
  p=np.array(list(map(float,text.splitlines()[0].split())))
  return max(abs(p[1:7]-native0))<.002 and abs(p[8]-start['vy'])<.0001
 except (ValueError,IndexError):return False
available=[f'f{i:02d}' for i in list(range(1,16))+[18,19,20]]
paths=[p for p in sorted((a.evidence/'build/ps2ref/answers').glob('f[0-9][0-9]')) if (p/'trace.tsv').exists()]
assert [p.name for p in paths]==available,'available recordings changed: inspect inventory, never silently skip'
def covered(ids):return sorted(ids)==available
assert not covered(available[:-1]);print('RED genuinely missing available case rejected')
sources={str(seed):hashlib.sha256(seed.read_bytes()).hexdigest()};metrics=[];counts={}
for side,flags in [('candidate',['-DCAR_DROP_RESTITUTION_OLD=0']),('previous',['-DCAR_DROP_RESTITUTION_OLD=1']),('default',[])]:
 subprocess.run(['cc','-O2','-Iviewer',*flags,'tests/cars/drop_protocol.c','viewer/col.c','-lm','-o',str(out/side)],cwd=ROOT,check=True)
for p in paths:
 report=p/'report.json';rep=json.loads(report.read_text());assert rep['ok'] and rep['state_sha256']=='2ccea2a1356587a59269fad65e9056ea6ba5d6278cc09830e36c297d9c2afe44'
 recipe=a.evidence/'tools/ps2ref/recipes'/(p.name+'.json');R=json.loads(recipe.read_text())
 assert all(w['col'].startswith(('car_cm[','car_vel[')) for w in rep['writes'])
 writes=[f"{w['done']} {w['last']} {int(w['col'].startswith('car_vel'))} {int(w['col'].split('[')[1][0])} {w['value']}" for w in rep['writes']]
 descriptor='880\n'+' '.join(map(str,values))+'\n'+str(len(writes))+'\n'+'\n'.join(writes)+'\n'
 pose=out/(p.name+'.txt');pose.write_text(descriptor)
 rows=list(csv.DictReader((p/'trace.tsv').open(),delimiter='\t'));ports={};logs={}
 for side in ['candidate','previous','default']:
  log=subprocess.check_output([out/side,ROOT/'build/level.shr',pose],cwd=ROOT,text=True)
  assert poseok(log);logs[side]=log;(out/(p.name+'-'+side+'.tsv')).write_text(log)
  ports[side]=np.array([[float(v) for v in l.split()] for l in log.splitlines()])
 assert logs['default']==logs['candidate'],'default no longer matches the accepted 0.18 candidate'
 if p==paths[0]:
  bad=values.copy();bad[23]+=1 # wrong native COM, not a mocked result
  badpose=out/'bad-com.txt';badpose.write_text(descriptor.replace(' '.join(map(str,values)),' '.join(map(str,bad))))
  badlog=subprocess.check_output([out/'default',ROOT/'build/level.shr',badpose],cwd=ROOT,text=True)
  assert not poseok(badlog);print('RED actual C replay with wrong native COM rejected')
  repeat=subprocess.check_output([out/'default',ROOT/'build/level.shr',pose],cwd=ROOT,text=True);assert repeat==logs['default'];print('PASS replay deterministic twice')
 for k,(lo,hi) in enumerate([(172,398),(412,598),(612,880)],1):
  rr=[r for r in rows if lo<=int(r['rel'])<=hi];peak=max(float(r['car_vel[1]']) for r in rr);incoming=min(float(r['car_vel[1]']) for r in rr)
  period=max(int(y['rel'])-int(x['rel']) for x,y in zip(rr,rr[1:]))/50
  row=dict(id=p.name,phase=k,native_peak=peak,native_incoming=incoming,capture_band=[peak,peak+16*period])
  for side,data in ports.items():
   seg=data[(data[:,0]>=lo)&(data[:,0]<=hi)];v=float(max(seg[:,8]));row[side+'_peak']=v;row[side+'_incoming']=float(min(seg[:,8]));row[side+'_pass']=peak<=v<=peak+16*period
   counts[side]=counts.get(side,0)+int(row[side+'_pass'])
  metrics.append(row)
 for source in [p/'trace.tsv',report,recipe]:sources[str(source)]=hashlib.sha256(source.read_bytes()).hexdigest()
 print(p.name,' '.join(f"p{r['phase']}:native{r['native_peak']:.3f}/candidate{r['candidate_peak']:.3f}/old{r['previous_peak']:.3f}" for r in metrics if r['id']==p.name),flush=True)
(out/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n');(out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
print('FAMILY DIAGNOSTIC',counts,'/',len(metrics),'episodes; available18, missingf16/f17; f01–f20 use teleported phases')
print('LIMIT: contact families are not isolated; use this set as diagnostic only, not as a coefficient acceptance gate')
print('AUDIT PASS available source inventory, real bad-COM/missing red, deterministic default=candidate; clean drop selects restitution')
raise SystemExit(0 if a.audit else int(counts['default']!=len(metrics)))
