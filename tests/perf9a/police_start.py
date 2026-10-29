"""Final NEW GAME policy: native model under loading, seven real appearances."""
import argparse,hashlib,json,re,struct,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path)
ap.add_argument('--stage',type=Path,default=Path('build/perf9a-simple-stage'))
a=ap.parse_args();runs={r['name']:r for r in json.loads(a.manifest.read_text())}
errors=[];proof=[]
for l in range(1,8):
    run=runs['police'+str(l)] if l in (4,7) else runs['memory'+str(l)]
    log=(R/run['run']/'smoke.txt').read_text();name='cHears' if l==7 else 'cPolice'
    loads=[x for x in log.splitlines() if x.startswith('MCR load '+name+' ')]
    spawns=[x for x in log.splitlines() if x.startswith('HNR police ')]
    chases=[x for x in log.splitlines() if x.startswith('HNR chase ')]
    if len(loads)!=1 or not spawns or not chases or log.find(loads[0])>log.find(chases[0]):errors.append(f'L{l}: model not loaded before native chase/appearance')
    if 'END' not in log.split() or 'MCRNONE' in log or 'MCR bad' in log:errors.append(f'L{l}: missing model/END')
    if 'MCRPREFETCH' in log:errors.append(f'L{l}: cancelled warning policy present')
    pack=a.stage/(f'l{l}' if l>1 else '')/f'msncars-l{l}.shr';b=pack.read_bytes();h=struct.unpack_from('<8I',b);model=None
    for i in range(h[3]):
        d=b[h[4]+176*i:h[4]+176*(i+1)]
        if d[:16].split(b'\0')[0].decode()==name:
            off,n=struct.unpack_from('<II',d,144);model=dict(bytes=n,sha256=hashlib.sha256(b[off:off+n]).hexdigest())
    if not model or not loads or f"bytes={model['bytes']}" not in loads[0]:errors.append(f'L{l}: wrong authored model')
    stats=[]
    for line in log.splitlines():
        if not line.startswith('STAT '):continue
        p=line.split();s=dict(zip(p[2::2],p[3::2]))
        if not int(s['frames']):continue
        stats.append(s)
        if float(s['max'])>33.4 or float(s['heapmin'])<13:errors.append(f'L{l}: frame/heap budget')
        for k in ('missed','readerr','allocfail','memfail','geskip','gebad','missvis'):
            if int(s[k]):errors.append(f'L{l}: {k}')
    if not stats:errors.append(f'L{l}: missing measured frames')
    proof.append(dict(level=l,run=run,model=name,source_model=model,loads=loads,spawns=spawns,stats=stats))
(R/'build/perf9a-simple-police-proof.json').write_text(json.dumps(dict(errors=errors,levels=proof),indent=2)+'\n')
for row in proof:print(row['level'],row['loads'],row['spawns'],'max',max((float(s['max']) for s in row['stats']),default=-1))
for e in errors:print('FAIL',e)
sys.exit(bool(errors))
