"""Compile once, run all seven production banks, reject genuine OLD paths."""
import json
import argparse
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('--packs',type=Path,default=ROOT/'build/audio-audit')
OUT=ap.parse_args().packs.resolve()
source=(ROOT/'viewer/main_collect.h').read_text()
selector=source[source.index('static void trafficMotorFrame('):source.index('static float cardHudT')]
template=(ROOT/'tests/sound/npc_catalog.c.in').read_text().replace('AUDIO_SOURCE',str(ROOT/'viewer/audio.c')).replace('SELECTOR',selector)
(OUT/'npc_catalog.c').write_text(template)
results=[]
for name,flags,files in [
 ('catalog',[],['tests/sound/catalog_host.c','viewer/sound.c','viewer/msn_audio.c']),
 ('race-old',['-DMUSIC_RACE_OLD=1'],['tests/sound/catalog_host.c','viewer/sound.c','viewer/msn_audio.c']),
 ('wreck-old',['-DCAR_WRECK_AUDIO_OLD=1'],['tests/sound/catalog_host.c','viewer/sound.c','viewer/msn_audio.c']),
 ('fallback-old',['-DCAR_PROFILE_FALLBACK_OLD=1'],['tests/sound/catalog_host.c','viewer/sound.c','viewer/msn_audio.c']),
 ('npc',[],[str(OUT/'npc_catalog.c'),'viewer/skid.c','viewer/car.c','viewer/col.c']),
 ('npc-old',['-DCAR_NPC_AUDIO_OLD=1'],[str(OUT/'npc_catalog.c'),'viewer/skid.c','viewer/car.c','viewer/col.c'])]:
 exe=OUT/name
 subprocess.run(['cc','-O2','-std=c11','-DAUDIO_HOST','-DSKIN_HOST','-DSKID_HOST','-Iviewer',*flags,*files,'-lm','-o',str(exe)],cwd=ROOT,check=True)
 for lv in range(1,8):
  p=subprocess.run([str(exe),str(OUT/f'l{lv}/audio')+'/'],capture_output=True,text=True)
  (OUT/f'{name}-l{lv}.log').write_text(p.stdout+p.stderr)
  expected=1 if name.endswith('-old') else 0
  last=p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr
  print(lv,name,last,flush=True)
  assert p.returncode==expected,(name,lv,p.returncode,p.stdout,p.stderr)
  if name=='race-old':assert 'FAIL street race starts authored event' in p.stdout
  if name=='wreck-old':assert 'FAIL wreck uses huskA engine and skid profile' in p.stdout
  if name=='fallback-old':assert 'FAIL undefined wreck horn does not borrow level horn' in p.stdout
  if name=='npc-old':assert 'FAIL line' in p.stdout
  results.append(dict(level=lv,mode=name,result=last,rc=p.returncode))
(OUT/'runtime.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS runtime L1-L7; races OLD7/7 and mission-car OLD7/7 rejected')
