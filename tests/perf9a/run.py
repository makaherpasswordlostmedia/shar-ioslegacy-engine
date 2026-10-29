"""Reproduce native memory/picture budgets with one immutable headless EBOOT.

Stock smoke_report rc is retained for every run, including the short debug
gagsnap scenes. No PSP deployment or exporter invocation.
"""
import argparse,datetime,hashlib,json,os,re,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('stage',type=Path)
ap.add_argument('--out',type=Path);a=ap.parse_args()
stage=a.stage.resolve();out=a.out or R/'build/perf9a'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out.mkdir(parents=True,exist_ok=True);boot=stage/'EBOOT.PBP'
sha=hashlib.sha256(boot.read_bytes()).hexdigest();result=[]
cases=[('gags-green','tests/perf9a/gags-green.txt',''),('gags-old','tests/perf9a/gags-old.txt','gagskinstreamold')]
cases += [('memory'+str(i),'tests/perf6/police_heap_l'+str(i)+'.txt','') for i in range(1,8)]
cases += [('police4','tests/perf9a/police-outdoor-l4.txt',''),('police7','tests/perf9a/police-outdoor-l7.txt','')]
cases += [('memory-old'+str(i),'tests/perf6/police_heap_l'+str(i)+'.txt','gagskinstreamold') for i in (1,4,7)]
cases += [('police-old','tests/perf6/police_old.txt','')]
for name,scn,flags in cases:
    assert hashlib.sha256(boot.read_bytes()).hexdigest()==sha,'stage EBOOT changed during series'
    env=os.environ.copy();env.update(SMOKE_HEADLESS='1',SMOKE_SCN=str(R/scn),SMOKE_MAXT='250',SHIP_LEVELS='2 3 4 5 6 7',SMOKE_FLAGS=flags)
    with (out/(name+'.log')).open('w') as f:
        p=subprocess.run(['bash','tools/smoke.sh',str(stage)],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
    match=re.search(r'отчёт: (.+?)/summary.txt',(out/(name+'.log')).read_text())
    result.append(dict(name=name,rc=p.returncode,run=match.group(1) if match else None,eboot_sha256=sha,
                       scenario_sha256=hashlib.sha256((R/scn).read_bytes()).hexdigest()))
    (out/'runs.json').write_text(json.dumps(result,indent=2)+'\n');print(result[-1],flush=True)
assert hashlib.sha256(boot.read_bytes()).hexdigest()==sha
