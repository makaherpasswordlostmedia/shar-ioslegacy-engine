#!/usr/bin/env python3
"""Disc leveli vs real common runtime, all seven levels. --old uses genuine pre-fix contract/pool."""
import argparse,json,os,re,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];os.chdir(ROOT)
OUT=ROOT/'build/arrest-c3';OUT.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--old',action='store_true');ap.add_argument('--pool-old',action='store_true');ap.add_argument('--hit-old',action='store_true');a=ap.parse_args();variant='old' if a.old else 'pool-old' if a.pool_old else 'hit-old' if a.hit_old else 'new'
source=subprocess.check_output(['bash','-c','V=viewer; source tools/bots/lib.sh; printf "%s" "$BOTS_LIB"'],text=True)
exe=OUT/f'host-{variant}'
cmd=['cc','-std=c11','-O2','-w','-DSKIN_HOST','-Iviewer','-Itools/bots']+(['-DHNR_LEVEL_C3_OLD=1'] if a.old else ['-DHNR_POOL_C3_OLD=1'] if a.pool_old else ['-DHNR_HIT_MODEL_C3_OLD=1'] if a.hit_old else [])
with (OUT/f'compile-{variant}.log').open('w') as f:
 if subprocess.run(cmd+['tests/hnr/levels/host.c']+shlex.split(source)+['-lm','-o',str(exe)],stdout=f,stderr=subprocess.STDOUT).returncode:sys.exit('FAIL compilation')
results=[];bad=0
for level in range(1,8):
 text=(ROOT/f'hit-and-run-web/source/game/scripts/missions/level{level:02d}/leveli.mfk').read_text()
 def args(op):return [v.strip().strip('"') for v in re.search(op+r'\s*\(([^)]*)\)',text)[1].split(',')]
 model,con=args('CreateChaseManager')[:2];count=args('SetNumChaseCars')[0];decay=args('SetHitAndRunDecay')[0]
 stage=ROOT/'build/ship_stage';pack=stage if level==1 else stage/f'l{level}'
 with (OUT/f'l{level}-{variant}.log').open('w') as log:
  rc=subprocess.run([str(exe),str(pack/'level.shr'),str(stage/'homer.shr'),str(pack/f'level{level:02d}.msn'),model,con,count,decay,str(level)],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,BW_NO_ROOMS='1',BW_NO_COLLECT='1',BW_NO_AUDIO='1')).returncode
 bad+=bool(rc);results.append(dict(level=level,model=model,con=con,count=int(count),decay=float(decay),rc=rc));print(f'L{level} {"FAIL" if rc else "PASS"}')
(OUT/f'report-{variant}.json').write_text(json.dumps(dict(variant=variant,source='owned disc leveli.mfk',levels=results),indent=2)+'\n')
print(f'RESULT {"FAIL" if bad else "PASS"} failures={bad}');sys.exit(bool(bad))
