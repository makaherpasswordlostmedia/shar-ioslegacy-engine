#!/usr/bin/env python3
"""Bounded parallel native campaigns, no network/AI. Each worker owns its collision scratch.
python3 tools/cartest/sandbox_batch.py --runs 6 --workers 6 --seconds 300
"""
import argparse
import collections
import concurrent.futures
import json
import fcntl
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import time
from sandbox import ROOT, HERE, ENGINE, atomic, sha, MacMeter

TOTAL_KEYS=('updates','hits','landings','transitions','bounces','suspicions','propImpacts','glassBreaks','stateHits')
CURRENT=ROOT/'build/sandbox/soak-current.json'

def soak(a):
    """Checkpoint complete seeds, retain interrupted attempts, freeze executable and input data."""
    if a.resume_latest:
        a.resume=Path(json.loads(CURRENT.read_text())['path'])
    if a.resume:
        out=a.resume.resolve();meta=json.loads((out/'manifest.json').read_text())
        if meta.get('kind')!='native-soak-v1':raise ValueError('not a resumable soak campaign')
    else:
        out=ROOT/'build/sandbox/soaks'/(time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3));out.mkdir(parents=True)
        # Later game edits cannot silently change this campaign or its replay inputs.
        shutil.copy2(a.level,out/'level.shr');shutil.copy2(a.roads,out/'roads.bin')
        binary=out/'swarm'
        sources=[HERE/'sandbox.c',HERE/'cartest.c',*ENGINE,*sorted((ROOT/'viewer').glob('*.h'))]
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
        subprocess.run(['cc','-std=c99','-O2',str(HERE/'sandbox.c'),*[str(p) for p in ENGINE],'-lm','-o',str(binary)],check=True)
        if source_hashes!={str(p.relative_to(ROOT)):sha(p) for p in sources}:raise RuntimeError('sources changed while compiling; retry with a fresh campaign')
        meta=dict(kind='native-soak-v1',created=time.time(),cars=a.cars,workers=a.workers,seconds=a.seconds,seed=a.seed,
                  emit=600,sourceHashes=source_hashes,files={p:sha(out/p) for p in ('swarm','level.shr','roads.bin')},
                  platform=os.uname().machine,compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0],
                  notes=['30-second independent episodes, not persistent-world testing','Only L1 when using the default level',
                         'Completion is not gameplay acceptance; observations require review','Interrupted seeds restart from tick zero; old attempts remain'])
        atomic(out/'manifest.json',meta)
    lock=(out/'campaign.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('This campaign is already running')
    if not (1<=meta['workers']<=8 and 1<=meta['cars']<=256 and 1<=meta['seconds']<=3600):raise ValueError('invalid saved settings')
    for name,digest in meta['files'].items():
        if sha(out/name)!=digest:raise ValueError('campaign input changed: '+name)
    if (out/'STOP').exists():(out/'STOP').rename(out/f'STOP-acknowledged-{time.time_ns()}')
    atomic(CURRENT,dict(path=str(out)))
    done={int(p.stem.split('-')[1]):json.loads(p.read_text()) for p in out.glob('complete-*.json')}
    active={};stop=[False];started=time.monotonic();reason='running';next_seed=meta['seed']
    def requested(*_):stop[0]=True
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    try:meter=MacMeter()
    except OSError:meter=None
    cpu=None
    def save():
        totals={k:sum(r['totals'][k] for r in done.values()) for k in TOTAL_KEYS}
        atomic(out/'status.json',dict(kind='native-soak-v1',path=str(out),pid=os.getpid(),updatedAt=time.time(),
            status=reason,completedSeeds=len(done),workers=meta['workers'],active=[dict(seed=s,pid=j['proc'].pid,trace=j['trace'].name) for s,j in active.items()],
            totals=totals,systemCpu=cpu,elapsedThisSession=time.monotonic()-started,limitMinutes=a.soak_minutes,
            result='observations pending review; not a gameplay PASS'))
    def launch(seed):
        tag=f'seed-{seed}-attempt-{secrets.token_hex(3)}';trace=out/(tag+'.ndjson');log=out/(tag+'.log')
        f=trace.open('w');err=log.open('w')
        cmd=[str(out/'swarm'),'--level',str(out/'level.shr'),'--roads',str(out/'roads.bin'),
             '--cars',str(meta['cars']),'--ticks',str(meta['seconds']*60),'--emit',str(meta['emit']),'--seed',str(seed)]
        p=subprocess.Popen(cmd,stdout=f,stderr=err,start_new_session=True)
        active[seed]=dict(proc=p,trace=trace,log=log,out=f,err=err,started=time.monotonic(),command=cmd)
        save()
    print(json.dumps(dict(path=str(out),minutes=a.soak_minutes,workers=meta['workers'],carsPerWorker=meta['cars'])),flush=True)
    try:
        while True:
            cpu=meter.sample() if meter else None
            for seed,job in list(active.items()):
                code=job['proc'].poll()
                if code is None:
                    if time.monotonic()-job['started']>600:reason='worker_timeout';stop[0]=True
                    continue
                job['out'].close();job['err'].close();del active[seed]
                if code:
                    atomic(out/f'failed-{seed}-{time.time_ns()}.json',dict(seed=seed,returncode=code,trace=job['trace'].name,log=job['log'].name))
                    reason='native_failure';stop[0]=True;continue
                result=summarize(job['trace']);last=result['final']
                if last['tick']!=meta['seconds']*60 or last['updates']!=meta['seconds']*60*meta['cars']:raise RuntimeError('incomplete seed returned success')
                item=dict(seed=seed,trace=job['trace'].name,command=job['command'],totals={k:last[k] for k in TOTAL_KEYS},
                          events=result['events'],glassCovered=last['glassCovered'],glassTotal=last['glassTotal'],coverage=last['coverage'])
                atomic(out/f'complete-{seed}.json',item);done[seed]=item;save()
            if stop[0]:
                if reason=='running':reason='interrupted'
                break
            if time.monotonic()-started>=a.soak_minutes*60:reason='time_limit';break
            if (out/'STOP').exists():reason='requested_stop';break
            if shutil.disk_usage(out).free<10*1024**3:reason='disk_reserve';break
            if sum(p.stat().st_size for p in out.iterdir() if p.is_file())>a.max_gib*1024**3:reason='data_limit';break
            while len(active)<meta['workers']:
                while next_seed in done or next_seed in active:next_seed+=1
                launch(next_seed);next_seed+=1
            save();time.sleep(1)
    except BaseException:
        reason='runner_error';raise
    finally:
        for seed,job in list(active.items()):
            job['proc'].terminate()
        for seed,job in list(active.items()):
            try:job['proc'].wait(timeout=5)
            except subprocess.TimeoutExpired:job['proc'].kill();job['proc'].wait()
            job['out'].close();job['err'].close()
        active.clear();save();fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    return 1 if reason in ('native_failure','worker_timeout','runner_error') else 0

def summarize(path):
    last=None;events=[];frames=0
    for line in path.open():
        item=json.loads(line)
        if item['type']=='frame':last=item;frames+=1
        else:events.append(item)
    if not last or not last['cars'] or not last['updates']:raise ValueError('empty campaign')
    return dict(final=last,frames=frames,events=dict(collections.Counter(x['kind'] for x in events)),
                review=[e for e in events if e['kind'] not in ('foliage','height-transition')])

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--level',type=Path,default=ROOT/'build/level.shr')
    ap.add_argument('--roads',type=Path,default=ROOT/'build/sandbox/roads-l1.bin')
    ap.add_argument('--runs',type=int,default=6);ap.add_argument('--workers',type=int,default=6)
    ap.add_argument('--seconds',type=int,default=300);ap.add_argument('--cars',type=int,default=96);ap.add_argument('--seed',type=int,default=100)
    ap.add_argument('--soak-minutes',type=float,default=0);ap.add_argument('--resume',type=Path)
    ap.add_argument('--resume-latest',action='store_true');ap.add_argument('--max-gib',type=float,default=4)
    # ночной прогон (night.py): своя новая папка пакета и частота кадров в трассе (600 = как в долгой кампании, ~5 МБ на серию)
    ap.add_argument('--out',type=Path);ap.add_argument('--emit',type=int,default=60)
    a=ap.parse_args()
    if not (1<=a.runs<=100 and 1<=a.workers<=8 and 1<=a.seconds<=3600 and 1<=a.cars<=256 and 1<=a.emit<=600):ap.error('bounded settings: runs 1..100, workers 1..8, seconds 1..3600, cars 1..256, emit 1..600')
    if a.soak_minutes or a.resume or a.resume_latest:
        if not 0<a.soak_minutes<=240 or not .1<=a.max_gib<=20:ap.error('soak minutes >0..240; max GiB .1..20')
        return soak(a)
    out=a.out.resolve() if a.out else ROOT/'build/sandbox/batches'/(time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
    out.mkdir(parents=True)   # новая папка: завершённые серии не перезаписываются
    binary=out/'swarm';subprocess.run(['cc','-std=c99','-O2',str(HERE/'sandbox.c'),*[str(p) for p in ENGINE],'-lm','-o',str(binary)],check=True)
    common=[str(binary),'--level',str(a.level.resolve()),'--roads',str(a.roads.resolve()),'--cars',str(a.cars),'--ticks',str(a.seconds*60),'--emit',str(a.emit)]
    atomic(out/'manifest.json',dict(settings={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        command=common,hashes={str(p):sha(p) for p in (binary,a.level,a.roads,HERE/'sandbox.c',HERE/'cartest.c',*ENGINE)},
        result='stress observations; no autonomous map editing or claim of complete route coverage'))
    def run(i):
        path=out/f'seed-{a.seed+i}.ndjson';cmd=common+['--seed',str(a.seed+i)]
        with path.open('w') as f, path.with_suffix('.log').open('w') as log:
            result=subprocess.run(cmd,stdout=f,stderr=log,timeout=600)
        if result.returncode:raise RuntimeError(f'seed {a.seed+i}: native failure {result.returncode}')
        summary=summarize(path);summary['seed']=a.seed+i;return summary
    started=time.monotonic();results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as executor:
        for result in executor.map(run,range(a.runs)):
            results.append(result);atomic(out/'results.json',dict(runs=results,complete=len(results)==a.runs,elapsed=time.monotonic()-started))
    totals={key:sum(r['final'][key] for r in results) for key in ('updates','hits','landings','transitions','bounces','suspicions','propImpacts','glassBreaks','stateHits')}
    # Coverage counts are intentionally not summed: workers may visit the same voxel.
    atomic(out/'summary.json',dict(totals=totals,wallSeconds=time.monotonic()-started,workers=a.workers,
          runs=len(results),simulatedCarHours=a.seconds*a.cars*a.runs/3600,reviewCases=sum(len(r['review']) for r in results)))
    print(json.dumps(dict(path=str(out),**totals,wallSeconds=time.monotonic()-started),ensure_ascii=False))

if __name__=='__main__':raise SystemExit(main() or 0)
