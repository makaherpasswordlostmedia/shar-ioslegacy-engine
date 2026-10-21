#!/usr/bin/env python3
"""Read-only A/B of supplied EBOOTs with fresh cloned data and smoke logs."""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def check_rest(report):
    # Smoke SHOT poses are rounded; the sub-mm bound comes from rest435.py.
    assert report['rc']==0 and len(report['shots'])==2
    assert not report['skidEvents'],report['skidEvents']
    positions=[list(map(float,s.split('pos ',1)[1].split())) for s in report['shots']]
    assert positions[0]==positions[1],positions
    return True

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--eboot',type=Path,required=True);p.add_argument('--headless',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--level',type=int,default=4);p.add_argument('--expect-rest',action='store_true');a=p.parse_args();out=a.out.resolve();assert not out.exists(),'Fresh run required';out.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['cp','-cR',str(a.stage),str(out)],check=True);subprocess.run(['cp','-c',str(a.eboot),str(out/'EBOOT.PBP')],check=True)
 x,z=(283.333333,283.333333) if a.level==4 else (188,279.9)
 (out/'scenario.txt').write_text(f'flag level {a.level}\nflag sfxlog\nscene settle\ngoto {x} {z} 0\nwait 5\nscene idle435\nshot idle_start\nwait 30\nshot idle_end\nend\n')
 (out/'smokelog').touch();env=dict(os.environ,TWINS_SMOKE=str(out/'smoke.txt'),TWINS_SHOTDIR=str(out),SDL_AUDIODRIVER='dummy',XDG_CONFIG_HOME=str(out/'test-config'),XDG_DATA_HOME=str(out/'test-data'))
 with (out/'headless.log').open('w') as log:r=subprocess.run([str(a.headless),'--graphics=software','--timeout=150',str(out/'EBOOT.PBP')],cwd=out,env=env,stdout=log,stderr=log,timeout=180)
 text=(out/'smoke.txt').read_text();assert re.search(r'^END',text,re.M),'No END';skids=[s for s in text.splitlines() if re.search(r'\bskid\b',s)];shots=[s for s in text.splitlines() if s.startswith('SHOT ')];report=dict(ebootSha256=hashlib.sha256(a.eboot.read_bytes()).hexdigest(),level=a.level,rc=r.returncode,skidEvents=skids,shots=shots);report['ended']=True
 if a.expect_rest:report['restSnapshotGate']=check_rest(report)
 (out/'rest435-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
