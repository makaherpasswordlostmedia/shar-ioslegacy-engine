#!/usr/bin/env python3
"""Actual bonus frame budget: menu render, race physics + render, no Vblank or log-write time.
Raw work_us is checked; io_us is reported without subtracting a spike. OLD disables
the real measurement and must be rejected for missing BONUSPERF frames.
"""
import argparse,json,math,re,sys
from pathlib import Path

def check(run):
    text=(run/'smoke.txt').read_text();errors=[];result={}
    if 'END' not in text.split():errors.append('incomplete native run')
    for kind,scene in [('menu','bonus_menu'),('race','bonus_race')]:
        rows=[dict(re.findall(r'(\w+)=(\S+)',l)) for l in text.splitlines()
              if l.startswith('BONUSPERF ') and f'kind={kind} ' in l and f'sc={scene} ' in l]
        if len(rows)<200:
            errors.append(kind+': missing BONUSPERF / fewer than200 frames');continue
        work=sorted(int(r['work_us'])/1000 for r in rows);p95=work[math.ceil(.95*len(work))-1]
        result[kind]=dict(frames=len(rows),p95_ms=p95,max_ms=max(work),
                          max_io_us=max(int(r['io_us']) for r in rows),
                          max_sim_us=max(int(r['sim_us']) for r in rows))
        if p95>11:errors.append(kind+': raw p95>11ms')
        if max(work)>33.4:errors.append(kind+': raw max>33.4ms')
        if kind=='race' and sum(int(r['sim_us'])>0 for r in rows)<200:errors.append('race: simulation was not measured')
    for l in text.splitlines():
        vals=dict(re.findall(r'(readerr|allocfail|geskip|memfail|gebad)[= ]([0-9]+(?:\.[0-9]+)?)',l))
        if any(float(v) for v in vals.values()):errors.append('native error: '+l)
    return errors,result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--measurement-old',action='store_true');a=p.parse_args()
    try:errors,result=check(a.run)
    except (OSError,ValueError) as e:print(str(e));sys.exit(2)
    result.update(status='FAIL' if errors else 'PASS',errors=errors,raw_p95_limit_ms=11,raw_max_limit_ms=33.4)
    print(json.dumps(result,indent=2));(a.run/'bonus-perf-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    if a.measurement_old:
        caught=len(errors)==2 and all('missing BONUSPERF' in e for e in errors)
        print('PASS actual OLD measurement rejected' if caught else 'FAIL OLD not rejected');sys.exit(not caught)
    sys.exit(bool(errors))
