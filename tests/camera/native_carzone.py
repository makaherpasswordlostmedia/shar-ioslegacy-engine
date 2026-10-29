#!/usr/bin/env python3
"""Actual carZoneStep versus typed original camera, using dense bodies and sparse eyes."""
import json
import math
from pathlib import Path
import subprocess
from native_ps2 import ROOT, CLASSES, native_runs


def angle(u, v):
    denom = math.sqrt(sum(x*x for x in u) * sum(x*x for x in v))
    if not denom:
        raise ValueError('zero eye vector')
    return math.degrees(math.acos(max(-1., min(1., sum(x*y for x, y in zip(u, v))/denom))))


def run(args):
    import carzone_ps2 as host
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'native_host'
    host.build(args.D + (['CARZONE_OFF'] if args.old else []), exe)
    pack = Path(args.pack).resolve()
    if not pack.is_file():
        raise ValueError('НЕТ ДАННЫХ: actual exported camera package ' + str(pack))
    errors, results = [], []
    kinds = {'-': 'FollowCam', 'r1_cam1': 'RailCam', 'z1_housejump': 'StaticCam'}
    for case in native_runs(args.evidence_root):
        lines = []
        for i, row in enumerate(case['rows']):
            m = [row[f'mat[{k}]'] for k in range(16)]
            T, R, U, F = m[12:15], m[0:3], m[4:7], m[8:11]
            points = [(0, (host.LO+host.HI)/2-host.ORIGIN, host.OFS)]
            points += [(w, y-host.ORIGIN, z+host.OFS) for z in (-host.HALF_L, host.HALF_L)
                       for w in (-host.HALF_W, host.HALF_W) for y in (host.LO, host.HI)]
            native_body = [tuple(T[k]+R[k]*w+U[k]*y+F[k]*z for k in range(3)) for w,y,z in points]
            body = [(x,y,-z) for x,y,z in native_body]
            speed = math.hypot(row['car_vel[0]'], row['car_vel[2]'])
            dt = (row['rel']-case['rows'][i-1]['rel'])/50 if i else .02
            lines.append(' '.join(str(x) for x in (dt,T[0],T[1],-T[2],speed,*[x for p in body for x in p])))
        output = subprocess.run([str(exe), str(pack)], input='\n'.join(lines)+'\n', text=True,
                                capture_output=True, check=True).stdout.splitlines()
        if len(output) != len(case['rows']):
            raise ValueError('incomplete actual C replay')
        expected, actual, samples = [], [], []
        for row, line in zip(case['rows'], output):
            frame = int(row['rel']); active = int(row['active_supercam_ptr'])
            vt = int(row[f'camera_vtable_{active:x}'])
            expected.append(CLASSES[vt]); cells = line.split(); actual.append(kinds.get(cells[0], cells[0]))
            ref = case['refs'].get(frame)
            if ref and ref['kind'] != 'FollowCam':
                T = [row[f'mat[{k}]'] for k in range(12,15)]
                ex,ey,ez = map(float,cells[1:4])
                eye = (ex,ey,-ez)  # Port -> native PS2, exactly one reflection.
                va, vr = [x-y for x,y in zip(eye,T)], [x-y for x,y in zip(ref['eye'],T)]
                a, d = angle(va,vr), abs(math.dist(eye,T)-math.dist(ref['eye'],T))
                ta, td = (6.,.6) if ref['kind']=='RailCam' else (1.,.2)
                good = actual[-1] == ref['kind'] and a<=ta and d<=td
                samples.append(dict(frame=frame,kind=ref['kind'],angle_deg=a,distance_error_m=d,
                                    eye=eye,original_eye=ref['eye'],pass_=good))
                if not good: errors.append(f"{case['name']} frame {frame}: actual eye FAIL {a:.3f}deg/{d:.3f}m")
        transitions = [int(case['rows'][i]['rel']) for i in range(1,len(expected)) if expected[i]!=expected[i-1]]
        wrong = [int(row['rel']) for row,a,b in zip(case['rows'],expected,actual)
                 if a!=b and not any(abs(row['rel']-f)<=4 for f in transitions)]
        if wrong: errors.append(f"{case['name']}: wrong camera type outside transition tolerance, first {wrong[0]}")
        results.append(dict(name=case['name'],trace_sha256=case['trace_sha256'],frames=len(output),
                            transitions=transitions,type_errors=len(wrong),actual_eye_samples=samples))
    samples = [x for r in results for x in r['actual_eye_samples']]
    if len(samples)<20: raise ValueError('insufficient true camera samples')
    proof = dict(status='FAIL' if errors else 'PASS',errors=errors,actual_eye_samples=len(samples),
                 results=results,limitation='Eyes only at actual P2S frames; no listener interpolation or synthetic dense eye')
    (out/'native-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    for case in results:
        s=case['actual_eye_samples']
        print(case['name'], 'type_errors',case['type_errors'],'eyes',len(s),'pass',sum(x['pass_'] for x in s),
              'max_distance_error',round(max((x['distance_error_m'] for x in s),default=0),4))
    print(proof['status']+' carzone vs actual tPointCamera')
    return bool(errors)
