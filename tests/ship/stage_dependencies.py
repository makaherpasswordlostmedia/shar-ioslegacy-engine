#!/usr/bin/env python3
"""Execute the actual production data loop: batch siblings and previous-stage dependency."""
from pathlib import Path
import subprocess,json,os,shutil,tempfile
ROOT=Path(__file__).resolve().parents[2]
def probe(old):
 d=Path(tempfile.mkdtemp(prefix='stage-',dir=ROOT/'build'));(d/'tools').mkdir();(d/'build').mkdir();(d/'stage/log').mkdir(parents=True)
 for n in ['ship_cache.py','ship_data.sh']:(d/'tools'/n).symlink_to(ROOT/'tools'/n)
 (d/'tools/export.py').write_text('import sys,pathlib\np=pathlib.Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True)\nwith open("calls","a") as f:f.write("batch\\n")\n(p/"one").write_text("first");(p/"two").write_text("second")\n')
 (d/'tools/derived.py').write_text('import sys,pathlib\np=pathlib.Path(sys.argv[1]);assert p.read_text()=="first"\npathlib.Path(sys.argv[2]).write_text("derived:"+p.read_text())\n')
 rules="""one|build/one|tools/export.py|python tools/export.py {outdir}
two|build/two|tools/export.py|python tools/export.py {outdir}
derived|build/derived|tools/derived.py {stage}/one|python tools/derived.py {stage}/one {out}
"""
 f=d/'tools/ship_files.sh';f.write_text("#!/bin/bash\ncat <<'RULES'\n"+rules+"RULES\n");f.chmod(0o755)
 script='ROOT="$PWD"; STAGE="$ROOT/stage"; LOG="$STAGE/log"; FORCE_LEVEL=0; USE=(); fail(){ echo "FAIL $*"; exit 1; }; step(){ echo "$*"; }; quality_check(){ :; }; . tools/ship_data.sh'
 env=dict(os.environ,SHIP_SIBLINGS_OLD=str(int(old)),PATH=str(ROOT/'.venv/bin')+os.pathsep+os.environ['PATH'])
 r=subprocess.run(['bash','-c',script],cwd=d,env=env,capture_output=True,text=True);(d/'log.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
 assert (d/'stage/derived').read_text()=='derived:first'
 assert not (d/'build/one').exists(),'dependency read canonical instead of staging'
 calls=(d/'calls').read_text().splitlines();assert len(calls)==(2 if old else 1),calls
 for n in ['one','two','derived']:assert (d/f'stage/{n}.inputs.sha256').exists()
 print(('OLD duplicate export caught' if old else 'PASS one batch + actual staged dependency'),len(calls),d)
 return str(d)
print(json.dumps(dict(new=probe(False),old=probe(True))))
