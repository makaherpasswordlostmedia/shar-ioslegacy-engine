#!/usr/bin/env python3
"""Diagnostic pairing from observed native pose; never tune a gate from its result."""
import argparse,json,subprocess
from pathlib import Path
import numpy as np

def matrix(v):
 a,b,c,d,e,f=v
 return np.array([[a,b,c],[b,d,e],[c,e,f]])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('trace',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--start',type=int);ap.add_argument('--gas',type=int,default=0);ap.add_argument('--recorded-input',action='store_true');ap.add_argument('--level',default='build/ship_stage/level.shr');ap.add_argument('--car-c',default='viewer/car.c');a=ap.parse_args()
 rows=json.loads(a.trace.read_text());row=next(x for x in rows if x['rel']==a.start) if a.start is not None else next(x for x in rows if x.get('phase')=='drive')
 start=row['rel'];frames=min(300,rows[-1]['rel']-start);a.out.mkdir(parents=True,exist_ok=True)
 angular=matrix([row['local'+str(i)] for i in range(27,33)])@np.array([row['local'+str(i)] for i in range(6,9)])
 values=[row['pm'+str(i)] for i in range(16)]+[row['vx'],row['vy'],row['vz']]+angular.tolist()+[row['local'+str(i)]+row['local'+str(i+3)] for i in range(3)]+[row['local'+str(i)] for i in range(13,19)]
 spec=a.out/'pose.txt';spec.write_text('famil_v '+str(frames)+' '+str(a.gas)+'\n'+' '.join(map(str,values))+'\n')
 if a.recorded_input:
  observed=[x for x in rows if start<=x['rel']<=start+frames]
  assert all('drive_throttle' in x for x in observed), 'trace lacks recorded controller input'
  schedule=[];idx=0
  for frame in range(1,frames+1):
   while idx+1<len(observed) and observed[idx+1]['rel']<=start+frame-1:idx+=1
   schedule.append(int(observed[idx]['drive_throttle']))
  with spec.open('a') as f:f.write('INPUTS '+str(frames)+'\n'+' '.join(map(str,schedule))+'\n')
 source=a.out/'replay.c';source.write_text(Path('tests/cars/native_replay.c').read_text().replace('../../viewer/car.c',str(Path(a.car_c).resolve())))
 binary=a.out/'replay';subprocess.run(['cc','-std=c11','-O2','-I','viewer',str(source),'viewer/col.c','-lm','-o',str(binary)],check=True)
 result=subprocess.run([str(binary),a.level,str(spec)],capture_output=True,text=True,check=True);(a.out/'replay.tsv').write_text(result.stdout);p=np.loadtxt(a.out/'replay.tsv')
 original=np.array([[x['rel']-start,x['x'],x['y'],-x['z'],x['cx'],x['cy'],-x['cz'],x['vx'],x['vy'],-x['vz'],x['upy']] for x in rows if start<=x['rel']<=start+frames])
 initial=np.max(abs(p[0,1:7]-original[0,1:7]));assert initial<.002,('initial pose/COM mismatch',initial)
 point_velocity_error=float(np.max(abs(p[0,15:18]-original[0,7:10])))
 assert point_velocity_error<.0001,('initial model-origin velocity mismatch',point_velocity_error)
 paired=np.array([next(v for v in p if v[0]==t) for t in original[:,0]])
 delta=paired[:,1:4]-original[:,1:4];report=dict(start=start,frames=frames,initial_error=initial,initial_model_velocity_error=point_velocity_error,velocity_space='Vehicle model origin; COM velocity includes omega cross model-to-COM lever',model_rmse=np.sqrt(np.mean(delta*delta,axis=0)).tolist(),final_port=paired[-1,1:4].tolist(),final_original=original[-1,1:4].tolist(),final_distance=float(np.linalg.norm(delta[-1])),recoveries=int(paired[-1,14]),note='diagnostic; whole original behaviour not accepted by initial agreement')
 report['input_source']='recorded held throttle at native lockstep intervals' if a.recorded_input else f'fixed first {a.gas} frames throttle'
 (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
