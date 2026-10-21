"""Opening does no cold pack/list read; real card interval preserves its 7.75 ms budget."""
import argparse,json,sys
from pathlib import Path
from PIL import Image,ImageChops
p=argparse.ArgumentParser();p.add_argument('booth',type=Path);p.add_argument('briefing',type=Path);p.add_argument('--compare',type=Path);a=p.parse_args()
errors=[];result={}
for label,run,scene in [('booth',a.booth,'typo_booth'),('briefing',a.briefing,'briefing_idle')]:
    text=(run/'smoke.txt').read_text(errors='replace')
    if 'END' not in text.split():errors.append(label+': no END')
    rows=[s.split() for s in text.splitlines() if s.startswith('STAT '+scene+' ')]
    if len(rows)!=1:errors.append(label+': no STAT');continue
    row=dict(zip(rows[0][2::2],rows[0][3::2]));result[label]=row
    if int(row['frames'])<100:errors.append(label+': too few frames')
    if float(row['max'])>33.4:errors.append(label+': max >33.4ms')
    if label=='briefing' and float(row['p95'])>7.75:errors.append('card p95 >7.75ms')
    for key in ('missed','missvis','readerr','allocfail','geskip','memfail','gebad'):
        if int(row[key]):errors.append(label+': '+key)
    if label=='booth' and 'PHONEV load warm=1 ' not in text:errors.append('cold screen/list I/O at booth opening')
if a.compare:
    result['pixels']={}
    for name in ['phone_a','phone_b','phone_c','phone_a2']:
        x=Image.open(a.booth/(name+'.png')).convert('RGB');y=Image.open(a.compare/(name+'.png')).convert('RGB')
        if x.size!=y.size:errors.append(name+': different image size');continue
        count=sum(p!=(0,0,0) for p in ImageChops.difference(x,y).getdata());result['pixels'][name]=count
        if count:errors.append(name+': changed pixels')
result.update(status='FAIL' if errors else 'PASS',errors=errors,
              note='Mixed typo_brief includes the talk camera transition; its separate STAT timing is retained, not labelled card timing')
(a.booth/'perf8-proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));sys.exit(bool(errors))
