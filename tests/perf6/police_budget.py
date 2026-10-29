"""Cold police appearance: unchanged 33.4 ms maximum and no model I/O during pursuit."""
import argparse, hashlib, json, re, struct, sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--pack',type=Path,default=Path('build/stage/msncars-l1.shr'));a=p.parse_args()
log=(a.run/'smoke.txt').read_text(errors='replace');errors=[]
if 'END' not in log.split():errors.append('no END')
if 'MCRNONE' in log or 'MCR bad' in log:errors.append('missing or failed model')
chases=[float(x) for x in re.findall(r'^HNR chase t=([\d.]+)',log,re.M)]
spawn=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in log.splitlines() if line.startswith('HNR police ')]
loads=[dict(re.findall(r'(\w+)=([^\s]+)',line),name=line.split()[2]) for line in log.splitlines() if line.startswith('MCR load ')]
blob=a.pack.read_bytes();h=struct.unpack_from('<8I',blob);models={}
for i in range(h[3]):
    row=blob[h[4]+i*176:h[4]+(i+1)*176];name=row[:16].split(b'\0')[0].decode();off,size=struct.unpack_from('<II',row,144)
    models[name]=dict(bytes=size,sha256=hashlib.sha256(blob[off:off+size]).hexdigest())
if len(chases)!=1 or len(spawn)!=1 or spawn[0].get('police')!='1':errors.append('missing native chase/spawn')
police=[r for r in loads if r['name']=='cPolice']
if len(police)!=1:errors.append('police model must load once')
elif police[0]['name'] not in models or int(police[0]['bytes'])!=models[police[0]['name']]['bytes']:errors.append('wrong native model size')
elif not chases or float(police[0]['t'])>=chases[0]:errors.append('cold police model read during pursuit')
rows=[]
for line in log.splitlines():
    if not line.startswith('STAT '):continue
    parts=line.split();row=dict(zip(parts[2::2],parts[3::2]));row['scene']=parts[1]
    if int(row['frames'])==0:continue
    rows.append(row)
    if float(row['max'])>33.4:errors.append(row['scene']+': max '+row['max']+' > 33.4 ms')
    for key in ('missed','missvis','readerr','allocfail','geskip','memfail','gebad'):
        if int(row[key]):errors.append(row['scene']+': '+key+'='+row[key])
if not rows or sum(int(r['frames']) for r in rows)<180:errors.append('insufficient measured frames')
proof=dict(status='FAIL' if errors else 'PASS',errors=errors,rows=rows,chases=chases,spawn=spawn,loads=loads,source_pack_sha256=hashlib.sha256(blob).hexdigest(),police_model=models.get('cPolice'))
(a.run/'police-budget.json').write_text(json.dumps(proof,indent=2)+'\n')
for row in rows:print(row['scene'],'p95',row['p95'],'max',row['max'])
print('police loads',police,'spawn',spawn)
for error in errors:print('FAIL',error)
sys.exit(bool(errors))
