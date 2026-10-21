#!/usr/bin/env python3
"""Replay PS2 native SuperCam transitions through real carzone.c/roomcam.c.

The body box follows the existing carzone_ps2 probe (not a contact oracle).
OLD controls execute the actual former XZ speed and sticky-rail branches.
Exact 20 m/s threshold and collision-release criterion remain port rules.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import carzone_ps2 as cz

ROOT = Path(__file__).resolve().parents[2]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ps2-root', type=Path, default=ROOT.parent/'shar-psp-ps2-w')
    ap.add_argument('-D', action='append', default=[])
    ap.add_argument('--entry-only', action='store_true', help='partial gate: entry and first camera pose; exit is not accepted')
    ap.add_argument('--out', type=Path, default=ROOT/'build/camera/native_house')
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    fact_path = a.ps2_root/'knowledge/facts/ps2-house-native-supercam.yaml'
    fact = json.loads(fact_path.read_text())
    host = cz.HARNESS.replace('float dt, ref[3], sp, body', 'float dt, ref[3], sp, velocity[3], body')
    host = host.replace('"%f %f %f %f %f", &dt, &ref[0], &ref[1], &ref[2], &sp) == 5',
                        '"%f %f %f %f %f %f %f", &dt, &ref[0], &ref[1], &ref[2], &velocity[0], &velocity[1], &velocity[2]) == 7')
    host = host.replace('int k = carZoneStep', 'sp = carZoneSpeed(velocity);\n    int k = carZoneStep')
    src=a.out/'host.c'; src.write_text(host); exe=a.out/'host'
    subprocess.run(['cc','-std=c99','-O2',*[f'-D{x}' for x in a.D],'-I',str(ROOT/'viewer'),str(src),str(ROOT/'viewer/carzone.c'),str(ROOT/'viewer/roomcam.c'),'-lm','-o',str(exe)],check=True)
    pack=a.out/'carzone.shr';cz.pack(pack)
    results=[];good=True
    for case in fact['table'][:3]:
        rid=case['id'];path=a.ps2_root/'build/twins/o4'/rid/'trace.tsv'
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        evidence=next(e for e in fact['evidence']['runs'] if e['run'].endswith('/'+rid))
        if sha!=evidence['trace_sha256']:raise ValueError('Changed PS2 trace '+rid)
        rows=[];inputs=[];last=None
        for d in csv.DictReader(path.open(),delimiter='\t'):
            f=int(d['rel']);dt=(f-last)/50 if last is not None else 1/50;last=f
            r=dict(f=f,p=tuple(float(d[f'body{k}']) for k in (12,13,14)),fw=(float(d['body8']),float(d['body10'])),pitch=math.asin(max(-1,min(1,float(d['body9'])))),eye=tuple(float(d[f'cam_pos[{k}]']) for k in range(3)))
            velocity=[float(d[f'car_vel[{k}]']) for k in range(3)]
            ref=(r['p'][0],r['p'][1],-r['p'][2]);rows.append(r)
            inputs.append(' '.join(map(str,(dt,*ref,*velocity)))+' '+' '.join(' '.join(map(str,b)) for b in cz.body(r)))
        output=subprocess.run([str(exe),str(pack)],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True).stdout.splitlines()
        if len(output)!=len(rows) or len(rows)<100:raise ValueError('Missing replay samples '+rid)
        poses=[];cuts=[];prev='-'
        for r,line in zip(rows,output):
            v=line.split();name=v[0];eye=(float(v[1]),float(v[2]),-float(v[3]));poses.append((name,eye))
            if name!=prev:cuts.append((r['f'],name));prev=name
        # Independently measured native types. A two-frame Follow interval at70
        # may collapse to one cut; each boundary must stay within the existing ±4 PAL-frame tolerance.
        want = {'ps2_v95_house_50_native':[(266,'z1_housejump')],
                'ps2_v95_house_70_native':[(166,'r1_cam1'),(198,'z1_housejump')],
                'ps2_v95_house_200_native':[(148,'r1_cam1'),(216,'-')]}[rid]
        ok=len(cuts)==len(want) and all(n==wn and abs(f-wf)<=4 for (f,n),(wf,wn) in zip(cuts,want))
        if a.entry_only:
            ok=bool(cuts) and cuts[0][1]==want[0][1] and abs(cuts[0][0]-want[0][0])<=4
        print(('PASS' if ok else 'FAIL'),rid,'cuts',cuts,'PS2',want,'samples',len(rows));good &= ok
        results.append(dict(id=rid,trace_sha256=sha,samples=len(rows),cuts=cuts,expected=want,ok=ok))
        # Retain the established independent pose tolerances (6° rail, 1° static).
        for typ,cam in [('RailCam','r1_cam1'),('StaticCam','z1_housejump')]:
            starts=[t['frame'] for t in case['transitions'] if t['type']==typ]
            if not starts or (a.entry_only and typ=='StaticCam' and len(want)>1):continue
            start=starts[0];stop=next((t['frame'] for t in case['transitions'] if t['frame']>start),1<<30)
            angles=[];dist=[]
            for r,(name,eye) in zip(rows,poses):
                if not start+4<=r['f']<stop-4 or name!=cam:continue
                u=[x-y for x,y in zip(eye,r['p'])];v=[x-y for x,y in zip(r['eye'],r['p'])]
                angles.append(cz.ang(u,v));dist.append(abs(math.sqrt(sum(x*x for x in u))-math.sqrt(sum(x*x for x in v))))
            ma=sum(angles)/len(angles) if angles else math.inf;md=sum(dist)/len(dist) if dist else math.inf
            ok=ma<=(6 if typ=='RailCam' else 1) and md<=(.6 if typ=='RailCam' else .2)
            print(('PASS' if ok else 'FAIL'),rid,typ,'angle',round(ma,3),'distance',round(md,3),'samples',len(angles));good &= ok
            results.append(dict(id=rid,type=typ,angle=ma,distance=md,samples=len(angles),ok=ok))
        with (a.out/(rid+'.tsv')).open('w') as f:
            f.write('frame\tcamera\tx\ty\tz\n')
            for r,(n,e) in zip(rows,poses):f.write('\t'.join(map(str,(r['f'],n,*e)))+'\n')
    # Distant native jz2 jump uses FollowCam: the city's real zone picker must never override it.
    jpath=ROOT/'build/twins/o4/codex378_jz2_0702/camera.tsv'
    jrows=list(csv.DictReader(jpath.open(),delimiter='\t'))
    if len(jrows)<100:raise ValueError('Missing jz2 coverage')
    inputs=[]
    for i,d in enumerate(jrows):
        prev=jrows[max(0,i-1)];nxt=jrows[min(len(jrows)-1,i+1)]
        span=(float(nxt['frame'])-float(prev['frame']))/50 or 1
        velocity=((float(nxt['x'])-float(prev['x']))/span,float(d['vy']),(float(nxt['z'])-float(prev['z']))/span)
        pos=(float(d['x']),float(d['y']),float(d['z']))
        # Only zone eligibility is tested here; no claim about replayed FollowCam's pose.
        row=dict(p=pos,fw=(float(d['nx']),float(d['nz'])),pitch=0)
        inputs.append(' '.join(map(str,(.04,pos[0],pos[1],-pos[2],*velocity)))+' '+' '.join(' '.join(map(str,b)) for b in cz.body(row)))
    output=subprocess.run([str(exe),str(pack)],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True).stdout.splitlines()
    if len(output)!=len(jrows):raise ValueError('Lost jz2 samples')
    active=sum(line.split()[0]!='-' for line in output)
    ok=active==0;good &= ok
    print('PASS' if ok else 'FAIL','jz2 FollowCam control: zone overrides',active,'of',len(jrows))
    results.append(dict(id='codex378_jz2_0702',samples=len(jrows),zone_overrides=active,trace_sha256=hashlib.sha256(jpath.read_bytes()).hexdigest(),ok=ok))
    (a.out/'report.json').write_text(json.dumps(dict(ok=good,coverage='entry-and-first-pose' if a.entry_only else 'entry-exit-and-pose',defines=a.D,fact_sha256=hashlib.sha256(fact_path.read_bytes()).hexdigest(),results=results),ensure_ascii=False,indent=2)+'\n')
    return 0 if good else 1
if __name__=='__main__':sys.exit(main())

