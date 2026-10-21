"""Task 6: original house pose, director's 17:05 criterion <=11 ms; OLD must fail."""
import argparse, json, re, sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--old',action='store_true');a=p.parse_args()
log=(a.run/'smoke.txt').read_text(errors='replace');errors=[];rows=[]
if 'END' not in log.split():errors.append('no END')
for name in ('house3','house6'):
    scene=name+('_old' if a.old else '_new')
    found=[line.split() for line in log.splitlines() if line.startswith('STAT '+scene+' ')]
    if len(found)!=1:errors.append(scene+': missing STAT');continue
    row=dict(zip(found[0][2::2],found[0][3::2]));row['scene']=scene;rows.append(row)
    if int(row['frames'])<60:errors.append(scene+': insufficient measured frames')
    if float(row['p95'])>11:errors.append(scene+': p95 '+row['p95']+' > 11 ms')
    for key in ('missed','missvis','readerr','allocfail','geskip','memfail','gebad'):
        if int(row[key]):errors.append(scene+': '+key+'='+row[key])
out=dict(status='FAIL' if errors else 'PASS',budget_ms=11,criterion_source='Claude (дирижёр), ПАРА_ЖУРНАЛ.md 2026-10-09 17:05',old=a.old,errors=errors,rows=rows)
(a.run/('house-budget-old.json' if a.old else 'house-budget.json')).write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['scene'],'p95',row['p95'],'max',row['max'])
for error in errors:print('FAIL',error)
sys.exit(bool(errors))
