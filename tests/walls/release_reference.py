#!/usr/bin/env python3
"""Eligibility condition ordered by conductor15:14; full placement stays RED

Real immutable release implementation, same data/comparator, no release checkout writes
"""
import hashlib,io,json,os,shlex,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT);sys.path.insert(0,str(ROOT/'tools/twins'))
import walls_family as W
REF='ccdf4f6d5af18f0fec6933fec4cbe442f59952b7'
OUT=ROOT/'build/codex4-release-reference';OUT.mkdir(exist_ok=True);src=OUT/REF
if not src.exists():
 src.mkdir()
 data=subprocess.check_output(['git','archive',REF,'viewer','tools/bots','tools/twins/placement_light.c'])
 with tarfile.open(fileobj=io.BytesIO(data)) as t:t.extractall(src,filter='data')
lib=shlex.split(subprocess.check_output(['bash','-c','V=viewer; . tools/bots/lib.sh; echo "$BOTS_LIB"'],cwd=src,text=True))
exe=OUT/'placement'
with (OUT/'compile.log').open('w') as f:subprocess.run(['cc','-std=c11','-O2','-w','-DSKIN_HOST','-Iviewer','-Itools/bots','tools/twins/placement_light.c',*lib,'-lm','-o',exe],cwd=src,stdout=f,stderr=subprocess.STDOUT,check=True)
rawrun=W.run_side;rawbin=W.PL.light_bin
def capture(label,flags='',reference=False):
 W.PL.light_bin=(lambda:exe) if reference else rawbin
 W.run_side=lambda level,tag,cflags='':rawrun(level,label,cflags)
 rc=W.gate(1,flags);p=W.PL.out_dir(1)/'families'/('gate_red.json' if flags else 'gate_gate.json');r=json.loads(p.read_text());r['rc']=rc
 (OUT/(label+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');return r
old=capture('release_ref',reference=True);now=capture('current');red=capture('backside_old','-DCOL_FENCE_BACK_OLD=1')
W.PL.light_bin=rawbin;W.run_side=rawrun
def eligible(r,old):
 return (not r['ok'] and r['rc']==1 and not r['new'] and r['mismatch_now']<=r['mismatch_was']
         and len(r['back_family'])>0 and not r['back_fail'] and len(r['hedge_headon'])>0
         and {x['trial'] for x in r['hedge_fail']}=={'fence_f006_Ar'}
         and any(x['trial']=='fence_f006_Ar' for x in old['hedge_fail'])
         and not r['glance_bad'] and not r['jump_bad'] and len(r['slope_standing'])<r['slope_base'])
ok=eligible(now,old);assert not eligible(red,old),'actual backside regression was not rejected'
assert 'CAR_DROP_RESTITUTION_OLD 1' in (ROOT/'viewer/car.c').read_text()
result=dict(eligible=ok,full_placement_green=False,release_commit=REF,release_exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            level_sha256=hashlib.sha256((ROOT/'build/level.shr').read_bytes()).hexdigest(),known_fail='fence_f006_Ar/V135',
            current=now,release=old,red_backside_fail=len(red['back_fail']))
(OUT/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('PASS' if ok else 'FAIL','conductor eligibility: only pre-existing capsule condition red; full placement is still FAIL')
print('RED actual old backside implementation rejected:',len(red['back_fail']))
raise SystemExit(not ok)
