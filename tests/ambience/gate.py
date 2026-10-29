#!/usr/bin/env python3
"""All-level ambience data + live mixer/rooms. --room-old and --gain-old are deliberate red controls.
PS2 dB calibration is available only for L1, in tests/amb161/run.sh; other dBFS are port measurements.
"""
import argparse, json, math, os, re, struct, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT)
OUT=ROOT/'build/ambience-c3';OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/levels')]
import numpy as np
import sound_export as SE
import audio_export as AE
import ambience_check as AC
from interior_export import NAMES
ap=argparse.ArgumentParser();ap.add_argument('--room-old',action='store_true');ap.add_argument('--gain-old',action='store_true');ap.add_argument('--zones-old',action='store_true');ap.add_argument('--outdoor-old',action='store_true');ap.add_argument('--sound-source',default=os.environ.get('AMBIENCE_SOUND_SOURCE','viewer/sound.c'));ap.add_argument('--audio-source',default=os.environ.get('AMBIENCE_AUDIO_SOURCE','viewer/audio.c'));opts=ap.parse_args()
variant='room-old' if opts.room_old else 'gain-old' if opts.gain_old else 'zones-old' if opts.zones_old else 'outdoor-old' if opts.outdoor_old else 'new'
exe=OUT/f'host-{variant}'
cmd=['cc','-std=c11','-O2','-w','-DAUDIO_HOST','-Iviewer']
if opts.room_old:cmd+=['-DAMBIENCE_C3_OLD=1']
if opts.gain_old:cmd+=['-DAMB_GAIN=.6f']
if opts.outdoor_old:cmd+=['-DAMB422_OLD=1']
with (OUT/f'compile-{variant}.log').open('w') as log:
 if subprocess.run(cmd+['tests/ambience/host.c',opts.sound_source,opts.audio_source,'-lm','-o',str(exe)],stdout=log,stderr=subprocess.STDOUT).returncode:sys.exit('FAIL compilation')
amap=SE.ambience_map(); failed=0;report=[]
# Authored mixer levels from the disc, independently of the exported MODE table.
global_text=(SE.SND/'scripts/global.spt').read_text()
def volume(prefix):return float(re.search(r'Set'+prefix+r'AmbienceVolume\s*\(\s*([.\d]+)',global_text).group(1))
normal,foot=volume(''),volume('OnFoot')
# Existing documented room aliases, not new PS2 facts. Other interiors have no matching ambience event.
alias={'SpringfieldElementary':'School'}
key=lambda n:re.sub(r'[^a-z]','',re.sub(r'^L\d_','',n).lower())
events={key(m['event']):m for m in amap.values() if m['file'] and Path(m['file']).exists()}
for level in range(1,8):
 pack=ROOT/'build/ship_stage/audio' if level==1 else ROOT/f'build/ship_stage/l{level}/audio'
 if opts.zones_old:
  old=OUT/f'old-zones/l{level}';old.mkdir(parents=True,exist_ok=True)
  subprocess.run(['cp','-c',str(pack/'music.sap'),str(old/'music.sap')],check=True)
  b=bytearray((pack/'sfx.sab').read_bytes());ext,esz=struct.unpack_from('<II',b,80);count=struct.unpack_from('<I',b,ext+4)[0]
  for i in range(count):
   o=ext+8+16*i
   if b[o:o+4]==b'ZONE':b[o:o+4]=b'ZOLD'
  (old/'sfx.sab').write_bytes(b);pack=old
 bad=AC.check(level,pack,amap)
 tracks=AC.sap_tracks(pack/'music.sap');amb=[n for n,t in sorted(tracks.items(),key=lambda p:p[1]['index']) if t['bus']==1]
 spec=[f'START {amb[0]} -']; rooms=[]
 for f in sorted(SE.ART.glob(f'l{level}i*.p3d')):
  match=re.fullmatch(rf'l{level}i(\d+)\.p3d',f.name)
  if not match or int(match[1]) not in NAMES:continue
  room=NAMES[int(match[1])];rk=key(alias.get(room,room))
  m=events.get(rk) or next((v for k,v in events.items() if len(k)>=4 and rk.endswith(k)),None)
  tr=m['track'] if m else amb[0]
  spec.append(f'ROOM {room} {tr} {1 if m else 0}')
  rooms.append({'room':room,'track':tr,'source_event':m['event'] if m else None,'status':'disc-event' if m else 'port-rule-awaits-V82'})
  if m:
   t=tracks.get(tr);rs=AE.read_rsd(m['file']);data=rs['data']
   if rs['ch']==1:data=b''.join(data[i:i+16]*2 for i in range(0,len(data),16))
   if not t or t['bus']!=1 or not t['loop'] or t['data']!=data:bad.append(f'room {room}: missing or non-original loop {tr}')
 room_tracks={r['track']:r['room'] for r in rooms if r['source_event']}
 spec.extend(f'TRACK {t} {room_tracks.get(t,"-")}' for t in amb)
 # Small segments around every disc gate centre; resolve all overlapping volumes independently.
 zones=[]
 for fn,nm,kind,d,p3,vols in SE.locators(level):
  if kind!=0 or len(d)<4:continue
  event=amap.get(struct.unpack_from('<I',d)[0])
  if not event or not event['file'] or not Path(event['file']).exists():continue
  for vol in vols:
   R=np.asarray(vol['R']);norm=np.linalg.norm(R,axis=1);ax=R/np.where(norm>0,norm,1)[:,None]
   zones.append((nm,event['track'],vol['type'],np.asarray(vol['half'])*norm,ax,np.asarray(vol['t'])))
 def entry(z,a,b):
  nm,tr,typ,half,ax,t=z;la=ax@(a-t);lb=ax@(b-t)
  if typ==0:return 1. if float(lb@lb)<=half[0]**2 else -1.
  lo,hi=0.,1.
  for k in range(3):
   d=lb[k]-la[k]
   if abs(d)<1e-6:
    if abs(la[k])>half[k]:return -1.
   else:
    u,v=sorted(((-half[k]-la[k])/d,(half[k]-la[k])/d));lo=max(lo,u);hi=min(hi,v)
    if lo>hi:return -1.
  return lo
 for index,z in enumerate(zones):
  a=z[-1]+np.array([.1,0,0]);b=z[-1]-np.array([.1,0,0]);best=-1.;wanted=amb[0]
  for other in zones:
   hit=entry(other,a,b)
   if hit>=0 and hit>=best:best=hit;wanted=other[1]
  spec.append(f'GATE {index}-{z[0]} {wanted} '+ ' '.join(f'{v:.7g}' for v in [*a,*b]))
 disk=OUT/f'l{level}-spec.txt' ;disk.write_text('\n'.join(spec)+'\n')
 log=OUT/f'l{level}-{variant}.log'
 with log.open('w') as f:
  rc=subprocess.run([str(exe),str(pack)+'/',str(disk),str(normal),str(foot)],stdout=f,stderr=subprocess.STDOUT).returncode
 ok=not bad and rc==0;failed+=not ok
 measured=[line for line in log.read_text().splitlines() if line.startswith('MEASURE')]
 report.append({'level':level,'ambience_tracks':len(amb),'gates':len(zones),'rooms':rooms,'disk_errors':bad,'mixer_rc':rc,'measurements':measured})
 print(f'L{level} data {"FAIL" if bad else "PASS"} mixer {"PASS" if not rc else "FAIL"} tracks={len(amb)} rooms={len(rooms)}')
 for msg in bad:print('FAIL',msg)
(OUT/f'report-{variant}.json').write_text(json.dumps({'variant':variant,'source':'disc + actual sound/audio output','ps2_db_reference':'L1 only, V25; V82-V84 pending','owner_422_contract':{'dependency':'71ac25a','outdoor_db':-3,'authored_room_db':0,'sound_source':opts.sound_source,'audio_source':opts.audio_source},'levels':report},ensure_ascii=False,indent=2)+'\n')
print(f'RESULT {"PASS" if not failed else "FAIL"} failures={failed}')
sys.exit(bool(failed))
