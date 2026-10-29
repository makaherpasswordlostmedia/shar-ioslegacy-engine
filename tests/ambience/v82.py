#!/usr/bin/env python3
"""House L1 resource-flow acceptance. PS2 first-read bounds are NOT crossfade facts.
No emulator, export or production mutations. Freeze/hash supplied production source first.
"""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests/levels')]
import sound_export as SE
import audio_export as AE
from ambience_check import sap_tracks
ap=argparse.ArgumentParser()
ap.add_argument('--source-root',type=Path,default=ROOT)
ap.add_argument('--fact',type=Path,default=Path('/Users/USER/Downloads/shar-psp-ps2-w/knowledge/facts/ps2-house-ambience-entry-exit.yaml'))
ap.add_argument('--out',type=Path,default=ROOT/'build/ambience-c3/v82')
a=ap.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fact=json.loads(a.fact.read_text()); checks=[]
def check(name,ok):
 checks.append({'name':name,'ok':bool(ok)});print('CHECK',name,'PASS' if ok else 'FAIL')
check('original partial House evidence',fact['id']=='ps2-house-ambience-entry-exit' and fact['status']=='partial')
entry=next(r for r in fact['table'] if r['run'].endswith('house_entry_exit'))
exit=next(r for r in fact['table'] if r['run'].endswith('house_exit_action'))
check('actual original indoor/outdoor frames',entry['first_indoor_frame']==826 and exit['first_outdoor_frame']==66)
reads=fact['read_evidence'];check('original repeated room reads',sum('room_small_01.rsd' in r['path'] for r in reads['entry'])>3)
street=next(r for r in reads['exit'] if 'suburb_day_loop.rsd' in r['path'])
check('original street read bracket',street['preceding_png_frame']==70)
check('original upper read boundary documented','до80' in fact['answer'])
events=SE.ambience_map();room=next(m for m in events.values() if m['event']=='L1_House')
outdoor=next(m for m in events.values() if Path(m['file'] or '').name=='suburb_day_loop.rsd')
names=[outdoor['track'],room['track']];check('original room resource',Path(room['file']).name=='room_small_01.rsd')
pack=ROOT/'build/ship_stage/audio';tracks=sap_tracks(pack/'music.sap')
for m in [outdoor,room]:
 rs=AE.read_rsd(m['file']);data=rs['data']
 if rs['ch']==1:data=b''.join(data[i:i+16]*2 for i in range(0,len(data),16))
 t=tracks[m['track']];check('original VAG '+m['track'],t['data']==data and t['bus']==1 and t['loop']==1)
src=out/'source';src.mkdir(exist_ok=True);identity={}
for name in ['audio.c','sound.c']:
 p=a.source_root/'viewer'/name;(src/name).write_bytes(p.read_bytes());identity[str(p)]={'sha256':sha(p),'snapshot':str(src/name)}
base=['cc','-std=c11','-O2','-w','-DAUDIO_HOST','-I'+str(a.source_root/'viewer'),'-I'+str(ROOT/'viewer')]
exe=out/'host'
with (out/'compile.log').open('w') as log:
 for cmd in [base+['-Dfread=v82Read','-c',str(src/'audio.c'),'-o',str(out/'audio.o')],base+[str(ROOT/'tests/ambience/v82_host.c'),str(src/'sound.c'),str(out/'audio.o'),'-lm','-o',str(exe)]]:
  subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
args=[str(exe),str(pack)+'/',None,*names]
for name in names:
 t=tracks[name];args += [str(t['off']),str(t['off']+len(t['data']))]
logs={}; pcm={}
for mode,label in [(0,'new'),(1,'reference'),(2,'old-room'),(3,'plant-exit')]:
 cmd=args.copy();cmd[2]=str(out/(label+'.pcm'));cmd += [str(mode)]
 p=subprocess.run(cmd,capture_output=True,text=True,check=True);logs[label]=p.stdout;(out/(label+'.log')).write_text(p.stdout)
 pcm[label]=np.fromfile(cmd[2],dtype='<i2').reshape(-1,2)
measure={}; red={}
for label in ['new','old-room','plant-exit']:
 failures=[];measure[label]={}
 for phase,(start,n) in enumerate([(0,172),(172,259),(431,259)]):
  want=names[phase==1];match=re.search(rf'SETTLED phase={phase} name=(\S+) position=([\d.]+) underruns=(\d+)',logs[label])
  correct=bool(match and match[1]==want and float(match[2])>0)
  first=re.search(rf'READ phase={phase} frames=(\d+)',logs[label]);play=re.search(rf'PLAY phase={phase} frames=(\d+)',logs[label])
  # Last two seconds: phase-aligned independent original-resource request reference.
  raw=pcm[label][(start+87)*512:(start+n)*512];ref=pcm['reference'][(start+87)*512:(start+n)*512]
  same=np.array_equal(raw,ref);db=float(20*np.log10(np.sqrt(np.mean((raw.astype(float)/32768)**2))+1e-12))
  measure[label][str(phase)]={'track':match[1] if match else None,'first_read_seconds':int(first[1])/44100 if first else None,'first_playing_seconds':int(play[1])/44100 if play else None,'pcm_reference_equal':same,'dbfs':db,'frames':len(raw),'pcm_sha256':hashlib.sha256(raw.tobytes()).hexdigest()}
  for tag,ok in [('playing '+str(phase),correct),('actual resource read '+str(phase),bool(first)),('original resource PCM '+str(phase),same and db>-100)]:
   if label=='new':check(tag,ok)
   elif not ok:failures.append(tag)
 if label!='new':
  red[label]=failures
  (out/('red-'+label+'.log')).write_text('\n'.join('CHECK '+tag+' FAIL' for tag in failures)+f'\nRESULT FAIL failures={len(failures)}\n')
  critical='playing 1' if label=='old-room' else 'playing 2'
  check('genuine red '+label,critical in failures)
delay=measure['new']['2']['first_read_seconds']
timing={'native_seconds':delay,'native_anchor':'sndRoom(NULL) request in CPU fixture','ps2_read_bracket_seconds':[.08,.28],'ps2_anchor':'first outdoor frame66 after world transfer','directly_comparable':False,'status':'partial; different anchors without integrated door/iris/audio timing; no direct timing failure or fade equivalence inferred'}
print('TIMING RESIDUAL native first read',delay,'from sndRoom request; PS2 .08-.28 from outdoor frame66; different anchors, not a direct timing FAIL/crossfade fact')
report={'checks':checks,'sources':identity,'fact':{'path':str(a.fact),'sha256':sha(a.fact),'ps2_first_street_read_after_exit_bounds_seconds':[.08,.28],'meaning':'first resource read only; not PCM onset/crossfade'},'timing':timing,'pack_sha256':sha(pack/'music.sap'),'source_resources':{m['track']:{'path':str(m['file']),'sha256':sha(Path(m['file']))} for m in [outdoor,room]},'measurements':measure,'negative_controls':red,'limitation':'CPU host fixture; real reader/playing mixer and PCM, not integrated door/game/emulator or original waveform equivalence. Existing 0.5s port fade unchanged; native first-read delay measured separately.'}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
failed=sum(not c['ok'] for c in checks);print(f'RESULT {"FAIL" if failed else "PASS"} checks={len(checks)} failures={failed}');sys.exit(bool(failed))
