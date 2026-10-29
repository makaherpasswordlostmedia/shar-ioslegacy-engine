"""Run existing camera safety checks, then the director's complete regression series.

Every emulator invocation goes through tools/smoke.sh, headless and without audio.
Keep the staged EBOOT immutable while other source work continues.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]
stage=Path(sys.argv[1]).resolve();library=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve()
out.mkdir(parents=True,exist_ok=True)
identity=hashlib.sha256((stage/'EBOOT.PBP').read_bytes()).hexdigest()
result=dict(eboot_sha256=identity,camera=[])
env=os.environ.copy();env.update(SMOKE_HEADLESS='1',SCEN_ROOT=str(R),CAMIN_TAG='perf6camin')
for kind in ('car','foot'):
    original=(R/f'tests/camera/camin_{kind}.txt').read_text()
    for old in (True,False):
        name=f'perf6camin_{kind}_'+('red' if old else 'green')
        scenario=out/(name+'.txt');scenario.write_text(('flag camsafeold 1\n' if old else '')+original)
        env['SMOKE_SCN']=str(scenario)
        assert hashlib.sha256((stage/'EBOOT.PBP').read_bytes()).hexdigest()==identity
        log=out/(name+'.log')
        with log.open('w') as f:
            p=subprocess.run(['bash','tools/smoke.sh',str(stage)],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
        match=re.search(r'отчёт: (.+?)/summary.txt',log.read_text())
        run=(R/match.group(1)).resolve() if match else None
        if run:
            target=R/'build/twins/scen/full'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.symlink_to(run,target_is_directory=True)
        result['camera'].append(dict(name=name,scenario_sha256=hashlib.sha256(scenario.read_bytes()).hexdigest(),run=str(run),smoke_rc=p.returncode))
        (out/'suite.json').write_text(json.dumps(result,indent=2)+'\n')
        print(name,'retained',run,'raw smoke',p.returncode,flush=True)
env.pop('SMOKE_SCN',None)
with (out/'camera-gate.log').open('w') as f:
    camera=subprocess.run([sys.executable,'tests/camera/camin.py','--parse'],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
result['camera_gate_rc']=camera.returncode
print('camera safety gate',camera.returncode,flush=True)
regression=subprocess.run([sys.executable,'tools/twins/regress.py','--stage',str(stage),'--library',str(library),'--out',str(out/'regression')],cwd=R,env=env)
result['regression_rc']=regression.returncode
result['stage_unchanged']=hashlib.sha256((stage/'EBOOT.PBP').read_bytes()).hexdigest()==identity
(out/'suite.json').write_text(json.dumps(result,indent=2)+'\n')
sys.exit(bool(camera.returncode or regression.returncode or not result['stage_unchanged']))
