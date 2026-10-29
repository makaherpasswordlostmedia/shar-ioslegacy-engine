#!/usr/bin/env python3
"""Disk BindReward/AddPurchaseCarReward vs actual runtime and shipped purchase packages.
The --old-assets control reads an immutable pre-fix package snapshot, not a guessed failure.
--runtime-red builds GAME_SHOP_API=0: genuine completion must fail to deliver its rewards.
"""
import argparse, os, re, shlex, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
os.chdir(ROOT)
OUT=ROOT/'build/cars-c3'; OUT.mkdir(parents=True,exist_ok=True)
GAME=ROOT/'hit-and-run-web/source/game'
def calls(path,name):
 text=re.sub(r'//[^\n]*','',path.read_text(errors='replace'))
 return [[x.strip().strip('"') for x in m.group(1).split(',')] for m in re.finditer(name+r'\s*\(([^)]*)\)',text)]
def run(args,log,env=None):
 with log.open('w') as f:
  p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env)
 return p.returncode
ap=argparse.ArgumentParser();ap.add_argument('--old-assets');ap.add_argument('--runtime-red',action='store_true');ap.add_argument('--runtime-only',action='store_true');a=ap.parse_args()
source=subprocess.check_output(['bash','-c','V=viewer; source tools/bots/lib.sh; printf "%s" "$BOTS_LIB"'],text=True)
cc=['cc','-std=c11','-O2','-DSKIN_HOST','-Iviewer','-Itools/bots']
exe=OUT/('host-red' if a.runtime_red else 'host')
if a.runtime_red:cc+=['-DGAME_SHOP_API=0']
if run(cc+['tests/cars/catalog/host.c']+shlex.split(source)+['-lm','-o',str(exe)],OUT/'compile.log'):sys.exit('FAIL compilation')
rewards=calls(GAME/'scripts/missions/rewards.mfk','BindReward')
shipped=set(subprocess.check_output(['bash','tools/ship_files.sh'],env=dict(os.environ,SHIP_LEVELS='2 3 4 5 6 7'),text=True).splitlines())
failed=0
if not a.runtime_only:
 sys.path.insert(0,str(ROOT/'tools'))
 import shop_export as SX
for level in range(1,8):
 cars=[r for r in rewards if len(r)>=5 and r[2]=='car' and r[4]==str(level)]
 disk=OUT/f'l{level}-disk.tsv'; disk.write_text(''.join(f'{r[0]} {r[3]} {r[5] if len(r)>5 else 0} {r[6] if len(r)>6 else "-"}\n' for r in cars))
 sellers=calls(GAME/f'scripts/missions/level{level:02d}/leveli.mfk','AddPurchaseCarReward')
 seller_disk=OUT/f'l{level}-sellers.tsv'; seller_disk.write_text(''.join(f'{r[0]} {r[1]} {r[4]}\n' for r in sellers))
 pack=ROOT/'build/ship_stage' if level==1 else ROOT/f'build/ship_stage/l{level}'
 rc=run([str(exe),str(pack/'level.shr'),str(ROOT/'build/ship_stage/homer.shr'),str(pack/f'level{level:02d}.msn'),str(disk),str(seller_disk)],OUT/f'l{level}-runtime{"-red" if a.runtime_red else ""}.log',env=dict(os.environ,BW_NO_TRAFFIC='1',BW_NO_ROOMS='1',BW_NO_COLLECT='1',BW_NO_AUDIO='1'))
 ok=rc==0;failed+=not ok;print(f'L{level} runtime {"PASS" if ok else "FAIL"}')
 if a.runtime_only:continue
 try:
  assets=(Path(a.old_assets) if level==1 else Path(a.old_assets)/f'l{level}') if a.old_assets else pack
  names=[x.split()[0].lower() for x in (assets/'phonecars.txt').read_text().splitlines() if x.strip()]
  assert all(r[0].lower() in names for r in cars),'car absent from booth'
  assert SX.check(assets,level)==0,'purchase package check failed'
  if level>1:
   for fn in ['shop.shr','reward-0.shr','reward-1.shr','reward-2.shr']:
    assert f'l{level}/{fn}' in shipped,f'production ship list missing {fn}'
  print(f'L{level} assets PASS')
 except (AssertionError,FileNotFoundError) as e:
  failed+=1; print(f'L{level} assets FAIL {e}')
print(f'RESULT {"PASS" if not failed else "FAIL"} failures={failed}')
sys.exit(bool(failed))
