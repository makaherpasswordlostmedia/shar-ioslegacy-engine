"""Copy PSP results to durable backup, verify raw reports, write a compact analysis.
Does not delete results, change the console or claim simulator timings are hardware results.
"""
import argparse,csv,datetime,hashlib,json,shutil
from pathlib import Path
from collections import defaultdict
VARIANTS=('list_current','meshopt_hybrid','indexed_control','greedy_hybrid')
def analyze(folder,dataset):
    issues=[]
    lines=[]
    try:
        for x in (folder/'results.jsonl').read_text().splitlines():
            if x.strip():lines.append(json.loads(x))
    except (OSError,json.JSONDecodeError) as e:issues.append('log incomplete: '+str(e))
    complete=bool(lines and lines[-1].get('type')=='complete' and (folder/'COMPLETE.txt').exists() and not (folder/'STOPPED.txt').exists())
    if complete:
        for kind,n in {'start':1,'complete':1,'scene':3,'commands':12,'frame':12,'ge':42,'io':18,'oracle':4}.items():
            actual=sum(x.get('type')==kind for x in lines)
            if actual!=n:issues.append(f'{kind} records expected {n}, got {actual}')
    if any(x.get('type')=='oracle' and not x.get('pass') for x in lines):issues.append('on-device negative control failed')
    frames=[];io=[]
    for fn,out in [('frames.csv',frames),('io.csv',io)]:
        try:
            with (folder/fn).open() as f:out.extend(csv.DictReader(f))
        except OSError:issues.append(fn+' missing')
    if complete and len(frames)!=5040:issues.append('frame count expected 5040, got '+str(len(frames)))
    if complete and len(io)!=1152:issues.append('IO count expected 1152, got '+str(len(io)))
    groups=defaultdict(list)
    for row in frames:
        try:groups[(int(row['scene']),row['variant'],int(row['round']),int(row['inline_commands']))].append(int(row['work_us']))
        except (KeyError,TypeError,ValueError):issues.append('malformed frame row')
    for row in (x for x in lines if x.get('type')=='ge'):
        key=(row['scene'],row['variant'],row['round'],int(row['inline_commands']));values=sorted(groups[key])
        if len(values)!=120 or values[60]!=row['median_us'] or values[-1]!=row['max_us']:issues.append('GE summary mismatch '+str(key))
    comparisons=[]
    for si in range(3):
        reference=folder/f's{si}-v0.rgb565'
        if not reference.exists():
            if complete:issues.append(reference.name+' missing')
            continue
        a=reference.read_bytes()
        if len(a)!=278528:issues.append('bad reference frame size');continue
        for vi in range(4):
            p=folder/f's{si}-v{vi}.rgb565'
            if not p.exists():issues.append(p.name+' missing');continue
            b=p.read_bytes()
            if len(b)!=len(a):issues.append(p.name+' bad size');continue
            differences=sum(a[(y*512+x)*2:(y*512+x)*2+2]!=b[(y*512+x)*2:(y*512+x)*2+2] for y in range(272) for x in range(480))
            logged=[x for x in lines if x.get('type')=='frame' and x['scene']==si and x['variant']==VARIANTS[vi]]
            if len(logged)!=1 or logged[0]['different_pixels_vs_list']!=differences:issues.append('frame comparison mismatch '+p.name)
            comparisons.append(dict(scene=si,variant=VARIANTS[vi],different_pixels=differences))
        distinct={a[(y*512+x)*2:(y*512+x)*2+2] for y in range(272) for x in range(480)}
        if len(distinct)<8:issues.append(f'scene {si} suspiciously uniform, inspect capture')
    known={x['name']:x['sha256'] for x in dataset['scenes']}
    for row in (x for x in lines if x.get('type')=='scene'):
        if known.get(row['name'])!=row['sha256']:issues.append('unknown scene identity')
    io_errors=0;io_groups=defaultdict(list)
    for row in io:
        try:
            io_errors+=int(row.get('ok') or 0)!=1
            io_groups[(row['mode'],int(row['pass']),int(row['block_bytes']))].append(int(row['read_us']))
        except (KeyError,TypeError,ValueError):issues.append('malformed IO row')
    io_summary=[]
    for row in (x for x in lines if x.get('type')=='io'):
        key=(row['mode'],row['pass'],row['block']);values=sorted(io_groups[key])
        if len(values)!=64 or values[32]!=row['median_us'] or values[-1]!=row['max_us']:
            issues.append('IO summary mismatch '+str(key));continue
        throughput=row['block']*len(values)*1000000/sum(values) if sum(values) else 0
        if abs(throughput-row['bytes_per_second'])>1:issues.append('IO throughput mismatch '+str(key))
        io_summary.append(dict(mode=key[0],pass_number=key[1],block_bytes=key[2],median_us=values[32],max_us=values[-1],bytes_per_second=throughput))
    speed=[]
    for si in range(3):
        med={}
        for v in VARIANTS:
            vals=[x['median_us'] for x in lines if x.get('type')=='ge' and x['scene']==si and x['variant']==v and not x['inline_commands']]
            if len(vals)==3:med[v]=sorted(vals)[1]
        if 'list_current' in med:
            for v,t in med.items():speed.append(dict(scene=si,variant=v,median_of_round_medians_us=t,speedup_vs_current=med['list_current']/t if t else None))
    return dict(complete=complete,integrity_issues=issues,io_errors=io_errors,io_summary=io_summary,frame_comparisons=comparisons,render_summary=speed,limitations='Static opaque scenes only. Any pixel differences need review. Speed is not acceptance of the full game.')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--device',type=Path,default=Path('/Volumes/PSP/PSP/GAME/SHAROPT'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    runs=sorted(a.device.glob('run[0-9][0-9][0-9][0-9]'))
    if not runs:raise SystemExit('No runs found; results have not been collected')
    dataset=json.loads((a.device/'dataset.json').read_text());a.out.mkdir(parents=True,exist_ok=False)
    for n in ('package.json','dataset.json'):shutil.copy2(a.device/n,a.out/n)
    reports={}
    for run in runs:
        dest=a.out/run.name;shutil.copytree(run,dest);reports[run.name]=analyze(dest,dataset)
    manifest=[dict(path=str(p.relative_to(a.out)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in a.out.rglob('*') if p.is_file()]
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(a.out/'analysis.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
