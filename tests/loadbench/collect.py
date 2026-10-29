"""Preserve raw USB reports and validate before interpreting timings.
Partial runs stay partial. Synthetic host runs must remain labelled by caller.
"""
import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
from pathlib import Path


def stats(values):
    v=sorted(values)
    return dict(median=statistics.median(v),p95=v[math.ceil(.95*len(v))-1],
                p99=v[math.ceil(.99*len(v))-1],max=max(v),total=sum(v))


def expected_ids(dataset, group, round_, mode):
    ids=[b['id'] for b in dataset['blocks'] if b['group']==group]
    if mode:
        seed=0x93a51c7d+(round_-1)*97+group
        for n in range(len(ids),1,-1):
            seed=(seed*1664525+1013904223)&0xffffffff
            j=seed%n;ids[n-1],ids[j]=ids[j],ids[n-1]
    return ids


def analyze(run,dataset,expected_platform='PSP'):
    issues,rows,events=[],[],[]
    try:
        events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    except (OSError,ValueError) as e:
        issues.append('Events incomplete: '+str(e))
    starts=[x for x in events if x.get('type')=='start']
    if len(starts)!=1 or starts[0].get('version')!=dataset['version'] or starts[0].get('samples')!=dataset['expected_samples'] or starts[0].get('index_fnv')!=dataset['index_fnv']:
        issues.append('Start identity mismatch')
    if starts and starts[0].get('platform')!=expected_platform:
        issues.append('Platform mismatch: host-test reports are not PSP evidence')
    controls=[x for x in events if x.get('type')=='controls']
    if len(controls)!=1 or not all(controls[0].get(k) is True for k in ('valid_decode','changed_output_rejected','truncated_input_rejected','overrun_detected')):
        issues.append('Negative controls missing')
    names={p.name for p in run.glob('case*.csv')}
    if names!={f'case{i:03}.csv' for i in range(1,73)}:issues.append('72 case files required')
    for case in range(1,73):
        path=run/f'case{case:03}.csv'
        if not path.exists():continue
        zero=case-1;round_=zero//24+1;mode=zero//12%2;group=zero//3%4
        codec=(zero%3+(round_-1)+mode+group)%3
        ids=expected_ids(dataset,group,round_,mode)
        try:
            with path.open() as f:
                case_rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
            assert len(case_rows)==len(ids)
            for j,r in enumerate(case_rows):
                assert (r['case'],r['round'],r['mode'],r['group'],r['codec'],r['sample'],r['block'],r['ok'])==(case,round_,mode,group,codec,j,ids[j],1)
                b=dataset['blocks'][ids[j]]
                assert (r['raw_bytes'],r['stored_bytes'],r['compressed'])==(b['raw_bytes'],b['stored_bytes'][codec],int(bool(b['compressed_mask']&(1<<codec))))
                assert all(0<=r[k]<=10000000 for k in ('read_us','decode_us','flush_us','ready_us','verify_us'))
                assert r['ready_us']==r['read_us']+r['decode_us']+r['flush_us']
            saved=[e for e in events if e.get('type')=='case_saved' and e.get('case')==case]
            assert len(saved)==1 and (saved[0]['round'],saved[0]['mode'],saved[0]['group'],saved[0]['codec'],saved[0]['samples'])==(round_,mode,group,codec,len(ids))
            rows.extend(case_rows)
        except (AssertionError,KeyError,ValueError,TypeError) as e:
            issues.append(f'{path.name}: invalid samples ({type(e).__name__})')
    finished=[e for e in events if e.get('type')=='finished']
    if len(finished)!=1 or finished[0].get('samples')!=dataset['expected_samples'] or finished[0].get('cases')!=72 or not finished[0].get('readback_verified'):
        issues.append('Finished checkpoint missing')
    if len(rows)!=dataset['expected_samples']:issues.append('Sample total mismatch')
    marker=f"{dataset['version']}\n72 cases verified\n{dataset['expected_samples']} samples\n"
    if not (run/'COMPLETE.txt').exists() or (run/'COMPLETE.txt').read_text()!=marker:issues.append('Completion marker missing or incomplete')
    if (run/'STOPPED.txt').exists():issues.append('STOPPED marker present')
    summaries=[]
    if not issues:
        for mode in range(2):
            for g in range(4):
                raw=sum(r['ready_us'] for r in rows if r['mode']==mode and r['group']==g and r['codec']==0)
                for c in range(3):
                    subset=[r for r in rows if (r['mode'],r['group'],r['codec'])==(mode,g,c)]
                    # Full-size blocks separated to prevent short-tail latency comparisons.
                    full=[r for r in subset if r['raw_bytes']==dataset['groups'][g]['block_limit']]
                    timing=stats([r['ready_us'] for r in subset])
                    summaries.append(dict(mode=('sequential','shuffled')[mode],group=dataset['groups'][g],
                        codec=('raw','lz4','lz4hc12')[c],samples=len(subset),ready_us=timing,
                        read_us=stats([r['read_us'] for r in subset]),decode_us=stats([r['decode_us'] for r in subset]),
                        flush_us=stats([r['flush_us'] for r in subset]),verify_us=stats([r['verify_us'] for r in subset]),
                        sampled_total_speedup=raw/timing['total'] if timing['total'] else None,
                        full_size_samples=len(full),full_size_ready_us=stats([r['ready_us'] for r in full]) if full else None))
    return dict(complete=not issues,issues=issues,samples=len(rows),start=starts[0] if starts else None,
                finished=finished[0] if finished else None,summaries=summaries,
                limitation=dataset['limitations'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--device',type=Path,default=Path('/Volumes/PSP/PSP/GAME/SHAROPT'))
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    for n in ('lb_dataset.json','lb_package.json','lb_index.bin','LOAD_README.txt','EBOOT.PBP'):
        shutil.copy2(a.device/n,a.out/n)
    dataset=json.loads((a.out/'lb_dataset.json').read_text());results={};package_issues=[]
    package=json.loads((a.out/'lb_package.json').read_text())
    for entry in package['files']:
        path=a.device/entry['path']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            package_issues.append('Package identity changed: '+entry['path'])
    for run in sorted(a.device.glob('load[0-9][0-9][0-9][0-9]')):
        if run.is_dir():
            shutil.copytree(run,a.out/run.name);results[run.name]=analyze(a.out/run.name,dataset)
            if package_issues:
                results[run.name]['issues'].extend(package_issues);results[run.name]['complete']=False
                results[run.name]['summaries']=[]
    manifest=[dict(path=str(x.relative_to(a.out)),bytes=x.stat().st_size,sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in a.out.rglob('*') if x.is_file()]
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (a.out/'analysis.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({k:dict(complete=v['complete'],samples=v['samples'],issues=v['issues']) for k,v in results.items()},indent=2))
