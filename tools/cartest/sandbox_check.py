#!/usr/bin/env python3
"""Native positive/negative controls and deterministic fleet replay on real level data."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from sandbox import ROOT,HERE,ENGINE,atomic,sha

def main():
    out=ROOT/'build/sandbox/verification';out.mkdir(parents=True,exist_ok=True)
    binary=out/'swarm';fixture=out/'fixture'
    flags=['cc','-std=c99','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
    for source,dest in [('sandbox.c',binary),('sandbox_fixture.c',fixture),('props_swarm_check.c',out/'props-swarm')]:
        subprocess.run(flags+[str(HERE/source),*[str(p) for p in ENGINE],'-lm','-o',str(dest)],check=True)
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'}
    unit=subprocess.run([str(fixture)],env=env,capture_output=True,text=True)
    assert unit.returncode==0,unit.stdout+unit.stderr
    prop=subprocess.run([str(out/'props-swarm'),str(ROOT/'build/level.shr')],env=env,capture_output=True,text=True)
    assert prop.returncode==0,prop.stdout+prop.stderr
    args=[str(binary),'--level',str(ROOT/'build/level.shr'),'--roads',str(ROOT/'build/sandbox/roads-l1.bin'),'--cars','16','--ticks','600']
    def run(extra=()):
        r=subprocess.run(args+list(extra),env=env,capture_output=True,text=True,timeout=60)
        rows=[json.loads(l) for l in r.stdout.splitlines()]
        for row in rows:row.pop('elapsed',None);row.pop('cpuSeconds',None)
        return r,rows
    a,ar=run();b,br=run();assert a.returncode==b.returncode==0,(a.stderr,b.stderr)
    assert ar==br,'same seed diverged'
    c,cr=run(['--seed','8']);assert c.returncode==0 and ar!=cr,'different seed control did not change trajectory'
    nan,nr=run(['--inject','nan']);assert nan.returncode!=0 and 'nonfinite' in nan.stderr,'NaN escaped detector'
    pen,pr=run(['--inject','penetration']);assert pen.returncode==0 and any(r.get('kind')=='penetration' for r in pr),'overlap escaped detector'
    empty,er=run(['--cars','0']);assert empty.returncode==2 and not er,'empty fleet passed'
    with tempfile.NamedTemporaryFile(suffix='.shr') as f:
        f.write(b'SHR');f.flush();bad,_=run(['--level',f.name]);assert bad.returncode==2,'truncated pack passed'
    report=dict(result='PASS',probes=8,checks=['independent actor sweeps and shared object clocks','stacked supports and roof landing + peer impulse','same-seed determinism','different-seed negative control','NaN rejection','persistent overlap detection','empty fleet rejection','truncated pack rejection'],
        native=a.stderr,fixture=unit.stdout,objects=prop.stdout,hashes={str(p):sha(p) for p in [binary,fixture,out/'props-swarm',ROOT/'build/level.shr']},
        limitations=['Address/Undefined sanitizers only; macOS leak detection unavailable','not a proof of all routes or of PSP frame time'])
    atomic(out/'result.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
