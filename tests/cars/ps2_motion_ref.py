#!/usr/bin/env python3
"""Offline gas/drop evidence. No PS2 emulator; thresholds from capture intervals.

Gas: o4_gas +/- half the stored sample interval around frame160 (2s throttle).
Drop: true peak >= captured peak, <= peak + gravity * capture interval,
because the outgoing ballistic maximum can occur before the next stored sample.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--evidence',type=Path,default=ROOT.parent/'shar-psp')
ap.add_argument('--level',default='build/level.shr')
ap.add_argument('--candidate',action='store_true',help='explicitly enable the 0.18 experiment; default tests actual shipped policy')
a=ap.parse_args();out=ROOT/'build/ps2-motion-ref';out.mkdir(exist_ok=True)
gas=a.evidence/'build/twins/o4/o4_gas/trace.tsv'
drop=a.evidence/'build/codex-terminal/rob-rest/388/attempt8/original-drop/trace.json'
rows=list(csv.DictReader(gas.open(),delimiter='\t'))
speed=lambda r:math.hypot(float(r['car_vel[0]']),float(r['car_vel[2]']))
gr={int(r['rel']):speed(r) for r in rows}
dt=min(y-x for x,y in zip(sorted(gr),sorted(gr)[1:]))
low,high=(gr[160-dt]+gr[160])/2,(gr[160]+gr[160+dt])/2
result={'evidence':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (gas,drop)}}
fail=0
for tag,flags in [('green',[]),('red',['-DGAS_REF_OLD=1'])]:
    binary=out/f'gas_{tag}'
    subprocess.run(['cc','-O2','-DSKIN_HOST','-I','viewer',*flags,'tests/cars/gas_ref.c','viewer/car.c','viewer/col.c','-lm','-o',str(binary)],cwd=ROOT,check=True)
    v=float(subprocess.check_output([str(binary),a.level],cwd=ROOT,text=True))
    ok=low<=v<=high;result[f'gas_{tag}']={'speed':v,'native_2s':gr[160],'band':[low,high],'pass':ok}
    print(('PASS' if ok else 'FAIL')+f' gas {tag}: {v:.3f}; PS2 {gr[160]:.3f}, capture band {low:.3f}..{high:.3f}')
    fail+=ok if tag=='red' else not ok
r=json.loads(drop.read_text());start=next(x for x in r if x['rel']==54);frames=min(300,r[-1]['rel']-54)
iv=np.array([[start['local'+str(i)] for i in (27,28,29)], [start['local'+str(i)] for i in (28,30,31)], [start['local'+str(i)] for i in (29,31,32)]])
angular=iv@np.array([start['local'+str(i)] for i in (6,7,8)])
values=[start['pm'+str(i)] for i in range(16)]+[start['vx'],start['vy'],start['vz']]+angular.tolist()+[start['local'+str(i)]+start['local'+str(i+3)] for i in range(3)]+[start['local'+str(i)] for i in range(13,19)]
pose=out/'drop_pose.txt';pose.write_text(f'famil_v {frames} 0\n'+' '.join(map(str,values))+'\n')
peak=max(x['vy'] for x in r if x['rel']>=54)
period=max(y['rel']-x['rel'] for x,y in zip(r,r[1:]))/50
# Gravity16 comes from the native drop trace/fact, not the checked implementation.
band=[peak,peak+16*period]
source=out/'replay.c';source.write_text((ROOT/'tests/cars/native_replay.c').read_text().replace('../../viewer/car.c',str(ROOT/'viewer/car.c')))
for tag,flags in [('green',[]),('red',['-DPS2_RESTITUTION_OLD=1']),('previous',['-DCAR_DROP_RESTITUTION_OLD=1'])]:
    if tag=='green' and a.candidate:flags=['-DCAR_DROP_RESTITUTION_OLD=0']
    binary=out/f'drop_{tag}'
    subprocess.run(['cc','-O2','-I','viewer',*flags,str(source),'viewer/col.c','-lm','-o',str(binary)],cwd=ROOT,check=True)
    trace=subprocess.check_output([str(binary),a.level,str(pose)],cwd=ROOT,text=True)
    (out/f'drop_{tag}.tsv').write_text(trace)
    points=np.array([[float(v) for v in line.split()] for line in trace.splitlines()])
    native0=np.array([start[k] for k in ('x','y','z','cx','cy','cz')]);native0[[2,5]]*=-1
    error=float(np.max(abs(points[0,1:7]-native0)))
    assert error<.002, ('original pose/COM mismatch',error) # existing native_replay contract
    assert abs(points[0,16]-start['vy'])<.0001, 'original model velocity mismatch'
    v=max(points[:,16]);ok=band[0]<=v<=band[1]
    result[f'drop_{tag}']={'peak':float(v),'native_peak':peak,'capture_band':band,'initial_error':error,'pass':bool(ok)}
    print(('PASS' if ok else 'FAIL')+f' drop {tag}: {v:.3f}; PS2 {peak:.3f}, capture band {band[0]:.3f}..{band[1]:.3f}')
    fail+=ok if tag!='green' else not ok
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('RESULT', 'FAIL' if fail else 'PASS (green gas/drop, historical and previous drop negatives caught)')
raise SystemExit(bool(fail))
