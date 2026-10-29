"""Native heap >=13 MiB, exact gag pictures and bounded actual skin/track reads.

The debug gagsnap command reloads a whole room for every gag. Its unfiltered
smoke_report rc/FPS and raw room timings are retained separately in the proof;
they are not relabelled as gameplay streaming frames.
"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parents[2]
def rows(log):
    out=[]
    for line in log.splitlines():
        if line.startswith('STAT '):
            p=line.split(); d=dict(zip(p[2::2],p[3::2])); d['scene']=p[1]
            if int(d['frames']):out.append(d)
    return out
def runlog(run):return (R/run/'smoke.txt').read_text(errors='replace')
def memory(log):
    failures=[]; rs=rows(log)
    if 'END' not in log.split() or not rs:failures.append('missing END/STAT')
    for r in rs:
        if float(r['heapmin'])<13:failures.append(r['scene']+': heapmin '+r['heapmin']+' < 13 MiB')
        if float(r['max'])>33.4:failures.append(r['scene']+': max > 33.4 ms')
        for k in ('missed','readerr','allocfail','memfail','geskip','gebad','missvis'):
            if int(r[k]):failures.append(r['scene']+': '+k)
    if 'COLL stream error=' in log:failures.append('stream read rejected')
    return failures,rs

ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path)
ap.add_argument('--final-manifest',type=Path)
ap.add_argument('--without-skins',type=Path)
ap.add_argument('--old-memory',type=int,choices=(1,4,7))
ap.add_argument('--plant-picture',action='store_true');a=ap.parse_args()
runs={r['name']:r for r in json.loads(a.manifest.read_text())};errors=[];proof={}
if a.final_manifest:
    final={r['name']:r for r in json.loads(a.final_manifest.read_text())}
    for l in range(1,8):runs['memory'+str(l)]=final['memory'+str(l)]
if a.old_memory:
    errors,rr=memory(runlog(runs['memory-old'+str(a.old_memory)]['run']))
    print(json.dumps(dict(errors=errors,rows=rr),indent=2));sys.exit(bool(errors))
for l in range(1,8):
    r=runs['memory'+str(l)];fail,rr=memory(runlog(r['run']));errors+=fail
    if r['rc']:errors.append('memory'+str(l)+': raw smoke failed')
    proof['L'+str(l)]=rr
g=runs['gags-green'];o=runs['gags-old'];gl=runlog(g['run']);ol=runlog(o['run'])
rs=rows(gl);scenes={r['scene'] for r in rs}
for i in range(18):
    if 'gag'+str(i) not in scenes:errors.append('missing STAT gag'+str(i))
if 'END' not in gl.split() or 'END' not in ol.split():errors.append('missing gag END')
for r in rs:
    if float(r['heapmin'])<13 or float(r['max'])>33.4:errors.append(r['scene']+': measured budget')
    for k in ('missed','readerr','allocfail','memfail','geskip','gebad','missvis'):
        if int(r[k]):errors.append(r['scene']+': '+k)
streams=[dict(re.findall(r'(\w+)=([^\s]+)',x)) for x in gl.splitlines() if x.startswith('GAGSTREAM ')]
if len(streams)<18:errors.append('missing actual streamed loads')
if any(float(x['ms'])>33.4 for x in streams):errors.append('skin/track read > 33.4 ms')
pixels=[]
for i in range(18):
    new=np.asarray(Image.open(R/g['run']/f'gag{i}.png'))
    old=np.asarray(Image.open(R/o['run']/f'gag{i}.png'))
    if a.plant_picture and i==0:
        if not a.without_skins:ap.error('--plant-picture requires --without-skins DIR')
        new=np.asarray(Image.open(a.without_skins/'gag0.png'))
    n=int(np.any(new!=old,axis=2).sum());pixels.append(n)
    if n:errors.append(f'gag{i}: {n} changed pixels')
proof.update(status='FAIL' if errors else 'PASS',errors=errors,runs=runs,pixels=pixels,streams=streams,
             raw_gag_smoke_rc=[g['rc'],o['rc']],gag_stats=rs,
             raw_room_rows=[x for x in gl.splitlines() if x.startswith('ROOM ')],
             raw_debug_workmax=[x for x in gl.splitlines() if re.match(r'^\d',x)])
if not a.plant_picture:(R/'build/perf9a-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
for l in range(1,8):print('L'+str(l),proof['L'+str(l)])
print('pixels',pixels,'stream max',max((float(x['ms']) for x in streams),default=0))
for e in errors:print('FAIL',e)
sys.exit(bool(errors))
