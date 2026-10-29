#!/usr/bin/env python3
"""Read recorded native BODY fields; preserve exact trace hashes, never launch PS2"""
import csv,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OBS=ROOT.parent/'shar-psp-ps2-w'
fact=OBS/'knowledge/facts/ps2-moving-traffic-hit.yaml';F=json.loads(fact.read_text());result=[]
for case in F['table']:
 p=OBS/'build/twins/o4'/case['id']/'trace.tsv'
 assert hashlib.sha256(p.read_bytes()).hexdigest()==case['trace_sha256']
 rows=list(csv.DictReader(p.open(),delimiter='\t'))
 tail=[r for r in rows if int(r['rel'])>case['last_moving_frame']]
 assert len(tail)>300
 span=(int(tail[-1]['rel'])-int(tail[0]['rel']))/50
 assert abs(span-case['remaining_observation_s'])<1e-12
 speed=max(math.sqrt(sum(float(r[f'traffic_vel{i}'])**2 for i in range(3))) for r in tail)
 posspan=[max(float(r[f'traffic_body{i}']) for r in tail)-min(float(r[f'traffic_body{i}']) for r in tail) for i in [12,13,14]]
 assert all(float(r['traffic_mass0'])==2000 for r in tail)
 # Report raw residuals; never substitute legacy_mat/part-position for BODY
 result.append(dict(case=case['id'],sha256=case['trace_sha256'],native_hold_s=span,max_residual_body_speed=speed,body_axis_position_span=posspan))
 print(case['id'],'native BODY hold',span,'seconds; max residual',speed,'m/s; position spans',posspan)
out=ROOT/'build/traffic-rejoin';out.mkdir(exist_ok=True);(out/'native-source.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS frozen native BODY evidence; one speed case50.379, not a valid90km/h proof')
