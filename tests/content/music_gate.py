#!/usr/bin/env python3
"""Actual command dispatch + actual SAP/MEVT backend, independently read RMS matrices."""
import argparse, collections, hashlib, json, os, struct, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/missions')]
import rms, mfk
ap=argparse.ArgumentParser();ap.add_argument('--old',action='store_true');ap.add_argument('--old-data',action='store_true');ap.add_argument('--source',type=Path,default=ROOT.parent/'shar-psp/build');a=ap.parse_args()
OUT=ROOT/'build/content';GAME=ROOT/'hit-and-run-web/source/game';failed=0;report=[]
for level in (2,4,7):
 c=rms.read(GAME/f'sound/music/l{level}_music.rms');spec=[];expect={}
 for e in c.pools['events']['els']:
  if not c.owner(e[2]):continue
  matrix=c.el(e[2]);refs=c.store[matrix[2][0]];assert len(refs)==1
  state=c.el(refs[0]);name=c.store[state[2][0]];values=[c.store[x] for x in c.store[state[2][1]]]
  event=c.store[e[0]].replace('_getoutofcar','_get_out_of_car').replace('_Win','_win')
  assert len(values)==len(c.store[e[1]])
  for vi,value in enumerate(values):
   actions=c.store[c.store[e[1]][vi]]
   regions=[c.owner(c.el(act)[2][1])[1] for act in actions if c.el(act)[0] in ('play_region','push_region')]
   assert len(regions)<=1
   plan=c.region_streams(regions[0]) if regions else []
   files={('sound/music/'+c.stream_file(si)[1].replace('\\','/')+'.rsd').lower() for si in plan[0]} if plan else set()
   key=event+'@'+value;expect[key]=files;spec.append((name,value,event))
 source_states=[]
 for f in (GAME/f'scripts/missions/level{level:02d}').glob('*.mfk'):
  calls=mfk.parse_file(f)[0]
  source_states += [tuple(x.args[:2]) for x in calls if x.op=='SetMusicState']
 specpath=OUT/f'music-spec-l{level}.tsv';specpath.write_text(''.join('\t'.join(row)+'\n' for row in spec))
 audio=ROOT/f'build/ship_stage/l{level}/audio' if a.old_data else OUT/f'audio-l{level}'
 pack=json.loads((audio/'pack_report.json').read_text()) if (audio/'pack_report.json').exists() else None
 # New authored bytes have the encoder's name->disc-file manifest, independently compared to RMS.
 names={row['name']:row['file'].lower() for row in pack['music']} if pack else {}
 levelpath=ROOT/f'build/ship_stage/l{level}/level.shr';msn=ROOT/f'build/ship_stage/l{level}/level{level:02d}.msn'
 # The harness loads its explicit frozen audio directory; prevent bwData from
 # replacing the shared host table with the sibling release's old audio.
 env=dict(os.environ,BW_NO_AUDIO='1',BW_TRAFFIC=str(ROOT/f'build/ship_stage/l{level}/traffic.shr'),BW_MSNCARS=str(a.source/f'msncars-l{level}.shr'))
 exe=OUT/('music-old' if a.old else 'music-host')
 p=subprocess.run([str(exe),str(levelpath),str(a.source/'homer.shr'),str(msn),str(audio)+os.sep,str(specpath)],env=env,text=True,capture_output=True)
 (OUT/f'music-native-l{level}{"-old" if a.old else "-olddata" if a.old_data else ""}.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError(f'host L{level} failed {p.returncode}: {p.stderr}')
 actual_states=[];variants=[]
 for line in p.stdout.splitlines():
  row=line.split('\t')
  if row[0]=='ACT':
   actual_states.append((row[5],row[6]))
   ok=row[7]=='M'+row[5][7:] and row[8]==row[6] and row[9].endswith('@'+row[6]) and int(row[10])>=0
   failed+=not ok;print(f'COMMAND L{level}/{row[2]} phase={row[3]} stage={row[4]} {row[5]}={row[6]} {"PASS" if ok else "FAIL"} selected={row[9]}')
  elif row[0]=='VAR':
   key=row[3]+'@'+row[2];files=expect[key];code=int(row[6]);selected=row[5]
   # Old data has no variants, so missing key is independently red even without a file manifest.
   ok=row[4]==key and ((not files and code==0) or (files and code==1 and names.get(selected) in files))
   failed+=not ok;variants.append(key);print(f'MATRIX L{level} {key} {"PASS" if ok else "FAIL"} actual={selected} expected={sorted(files)}')
   report.append(dict(level=level,event=key,selected=selected,expected=sorted(files),passCase=bool(ok)))
 assert collections.Counter(actual_states)==collections.Counter(source_states),f'L{level}: command schedule differs from MFK'
 assert set(variants)==set(expect),f'L{level}: runtime omitted matrix row'
assert len(report)==32
for level in (1,3,5,6):
 import sound_export as S
 os.environ['C3_CONTENT_MUSIC_OLD']='1';old=S.mission_music(level);os.environ.pop('C3_CONTENT_MUSIC_OLD')
 new=S.mission_music(level);assert old==new,f'nonmatrix L{level} changed'
 print(f'NONMATRIX L{level} unchanged PASS')
(OUT/f'music-report{"-old" if a.old else "-olddata" if a.old_data else ""}.json').write_text(json.dumps(dict(cases=report,failures=failed),ensure_ascii=False,indent=2)+'\n')
print(f'RESULT {"FAIL" if failed else "PASS"} matrix=32 command=9 failures={failed}');raise SystemExit(bool(failed))
