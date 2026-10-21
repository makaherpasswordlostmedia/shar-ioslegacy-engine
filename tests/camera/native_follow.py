"""Sparse true-eye comparisons on original V104 trajectories; never use listener as eye."""
import json
import math
from pathlib import Path
from native_ps2 import jump_runs


def run(args):
    import follow_ps2 as host
    exe=Path(args.out); host.build(args.source,args.D,exe)
    cases=[]; errors=[]
    for case in jump_runs(args.evidence_root):
        rows=[]
        for row in case['rows']:
            fw=(row['mat[8]'],row['mat[10]']);ln=math.hypot(*fw) or 1
            callbacks=sum(bool(int(row[f'wheel{i}_contact_candidate'])&255) for i in range(4))
            # A means callback received, not independently proven force/support.
            # Feed absence/presence as the same wheel signal chaseCamUpdate uses.
            rows.append(dict(f=int(row['rel']),p=tuple(row[f'mat[{i}]'] for i in range(12,15)),
                             fw=(fw[0]/ln,fw[1]/ln),air=callbacks==0,slope=row['mat[9]']/ln))
        eyes=host.replay(exe,rows);by_frame={r['f']:(r,e) for r,e in zip(rows,eyes)}
        base_r,base_eye=by_frame[0];base_ref=case['refs'][0]
        base_h=base_eye[1]-base_r['p'][1];base_true_h=base_ref['eye'][1]-base_r['p'][1]
        base_pitch=math.degrees(math.atan2(base_eye[4]-base_eye[1],math.hypot(base_eye[3]-base_eye[0],base_eye[5]-base_eye[2])))
        base_true_pitch=math.degrees(math.asin(base_ref['forward'][1]))
        samples=[]
        for frame,ref in sorted(case['refs'].items()):
            if frame==0:continue
            r,e=by_frame[frame]
            phase='ramp' if frame==case['lip'] else 'air' if frame<case['landing'] else 'land'
            true_h=ref['eye'][1]-r['p'][1]-base_true_h;port_h=e[1]-r['p'][1]-base_h
            true_pitch=math.degrees(math.asin(ref['forward'][1]))-base_true_pitch
            port_pitch=math.degrees(math.atan2(e[4]-e[1],math.hypot(e[3]-e[0],e[5]-e[2])))-base_pitch
            tol=.6 if phase=='ramp' else .5
            good=abs(port_h-true_h)<=tol and (phase!='air' or abs(port_pitch-true_pitch)<=3)
            if phase!='land' and not good:errors.append(f"{case['name']} {frame} {phase}: height/pitch differs")
            samples.append(dict(frame=frame,phase=phase,original_height_delta=true_h,port_height_delta=port_h,
                                original_pitch_delta=true_pitch,port_pitch_delta=port_pitch,pass_=good,
                                gate=phase!='land',source_sha256=ref['sha256']))
        cases.append(dict(name=case['name'],trace_sha256=case['trace_sha256'],samples=samples))
    result=dict(status='FAIL' if errors else 'PARTIAL',errors=errors,cases=cases,
                actual_camera_snapshots=25,
                open='No typed original v28 speed series; no dense tPointCamera air pitch variance; land is diagnostic')
    exe.parent.mkdir(parents=True,exist_ok=True)
    exe.with_suffix('.native-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    for case in cases:
        for s in case['samples']:
            print(case['name'],s['frame'],s['phase'],'height_error',round(s['port_height_delta']-s['original_height_delta'],3),
                  'pitch_error',round(s['port_pitch_delta']-s['original_pitch_delta'],3),
                  'OPEN' if not s['gate'] else 'PASS' if s['pass_'] else 'FAIL')
    print(result['status']+' follow vs actual tPointCamera; '+result['open'])
    return 1 if errors else 2  # Partial coverage must not silently become a full green.
