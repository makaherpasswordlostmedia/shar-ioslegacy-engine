#!/usr/bin/env python3
"""SuperSprint RMS events + minigame.spt, native ADPCM, one shared bonus audio bank"""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import audio_export as A
import sound_export as S
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'build/bonus/audio');a=ap.parse_args()
 events={e:S.event_alts(1,e) for e in ['SuperSprint','Win_SuperSprint','Lose_SuperSprint']}
 assert len(events['SuperSprint'])==5 and len(events['Win_SuperSprint'])==len(events['Lose_SuperSprint'])==1
 music=[]
 for event,paths in events.items():
  for k in paths:
   p=A.game_path('sound/music/'+k+'.rsd');assert p
   music.append((Path(k).name,p,event=='SuperSprint',None))
 text=(ROOT/'viewer/bonus_play.h').read_text();block=text.split('static const char *const bnsVeh[] = {')[1].split('};')[0]
 vehicles=re.findall(r'"([^"\n]+)"',block);res,cars,_,_=A.load_scripts();canonical={k.lower():k for k in cars}
 assert len(vehicles)==43
 npcblock=text.split('static const char *const bnsNpcCar[] = {')[1].split('};')[0]
 race_vehicles=re.findall(r'"([^"\n]+)"',npcblock)
 profiles=[canonical[v.lower()] for v in dict.fromkeys(vehicles+race_vehicles)];assert len(profiles)==44
 sfx=list(dict.fromkeys(['countdown_beeps','small_crash','med_crash','lrg_crash']+[cars[n].get('HornClipName') for n in profiles if cars[n].get('HornClipName')]))
 report=A.build_pack(str(a.out),'famil_v',sfx,music,extra_cars=profiles,quiet=True)
 for level in [2,7]:
  assert all(S.event_alts(level,event)==paths for event,paths in events.items())
 sources=list((ROOT/'hit-and-run-web/source/game/sound/scripts').glob('*.spt'))
 sources += [ROOT/f'hit-and-run-web/source/game/sound/music/l{level}_music.rms' for level in [1,2,7]]
 for n in ['countdown_beeps','small_crash','med_crash','lrg_crash']:sources += [Path(A.game_path(f)) for f in res[n]['files']]
 sources += [Path(p) for _,p,_,_ in music]
 sources += [Path(A.game_path(x['file'])) for x in report['sfx']]
 report.update(events=events,policy='race first authored alternative loops; results once; not native timing/selection proof',source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 (a.out/'source.json').write_text(json.dumps(report,indent=2)+'\n')
 print('bonus native audio:',len(profiles),'profiles,',len(music),'streams, SAB', (a.out/'sfx.sab').stat().st_size,'SAP',(a.out/'music.sap').stat().st_size)
if __name__=='__main__':main()
