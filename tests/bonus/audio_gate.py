#!/usr/bin/env python3
"""Actual sound/audio lifecycle, native payloads, OLD and corrupted-result control"""
import hashlib,json,struct,subprocess,sys,os,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));import audio_export as A
BASE=R/'build/bonus/audio-gate';BASE.mkdir(parents=True,exist_ok=True)
O=Path(tempfile.mkdtemp(prefix='run-',dir=BASE));bank=Path(os.environ.get('BONUS_AUDIO_DATA', R/'build/bonus/audio')).resolve()
def resident(sab):
 assert sab[:4]==b'SAB1';_,nr,nf,nc,ro,vo,fo,co,data,size=struct.unpack_from('<10I',sab,4)
 scripts,profiles,_,_=A.load_scripts();mini=['countdown_beeps','small_crash','med_crash','lrg_crash'];rows={}
 for i in range(nr):
  row=ro+48*i;name=sab[row:row+24].split(b'\0')[0].decode();rows[name]=struct.unpack_from('<HHfffII',sab,row+24)
 for name in mini:
  variant,n,trim,p0,p1,flags,bus=rows[name];src=scripts[name]
  assert trim==1 and p0==1 and p1==1 and flags==0 and n==len(src['files'])
  for j,path in enumerate(src['files']):
   idx=struct.unpack_from('<H',sab,vo+(variant+j)*2)[0];off,blocks,ns,ls,le,rate,ch,_=struct.unpack_from('<IIIIIHBB',sab,fo+idx*32)
   raw=A.read_rsd(A.game_path(path));assert rate==raw['rate'] and ch==raw['ch'] and blocks==raw['nblk']
   assert sab[data+off:data+off+len(raw['data'])]==raw['data']
 names=[sab[co+i*152:co+i*152+16].split(b'\0')[0].decode().lower() for i in range(nc)]
 import re
 vehicles=re.findall(r'"([^"\n]+)"',(R/'viewer/bonus_play.h').read_text().split('static const char *const bnsVeh[] = {')[1].split('};')[0])
 npc=re.findall(r'"([^"\n]+)"',(R/'viewer/bonus_play.h').read_text().split('static const char *const bnsNpcCar[] = {')[1].split('};')[0])
 assert len(vehicles)==43 and all(n.lower() in names for n in vehicles+npc)
 first=struct.unpack_from('<H',sab,vo+rows['countdown_beeps'][0]*2)[0]
 return data+struct.unpack_from('<I',sab,fo+first*32)[0]
sab=(bank/'sfx.sab').read_bytes();data=resident(sab);print('GREEN 4 native minigame resources/43 menu + 3 NPC profiles')
bad=bytearray(sab);bad[data+2]^=1
try:resident(bad)
except AssertionError:print('RED actual ADPCM byte corruption rejected')
else:raise AssertionError('ADPCM corruption not caught')
def payloads(sap):
 assert sap[:4]==b'SAP1';n,off=struct.unpack_from('<II',sap,8);assert n==7
 report=json.loads((bank/'source.json').read_text());by={x['name']:x for x in report['music']}
 for i in range(n):
  row=off+i*64;name=sap[row:row+28].split(b'\0')[0].decode();src=A.read_rsd(str(Path(A.GAME)/by[name]['file']))
  start,blocks,ns,ls,le,rate,ch,flags,nxt,bus=struct.unpack_from('<IIIIIHBBhh',sap,row+28)
  assert rate==src['rate'] and blocks==src['nblk'] and ns==src['nsamp'] and ch==2
  raw=src['data'];expect=raw if src['ch']==2 else b''.join(raw[k:k+16]*2 for k in range(0,len(raw),16))
  assert sap[start:start+len(expect)]==expect
  assert bool(flags&1)==name.startswith('casio_tune') and nxt==-1
 return n
sap=(bank/'music.sap').read_bytes();print('GREEN native stream bytes/meta',payloads(sap))
bad=bytearray(sap);off=struct.unpack_from('<I',bad,12)[0]
for i in range(7):
 row=off+i*64
 if bytes(bad[row:row+28]).startswith(b'win_mini_game'):bad[row+51]|=1
try:payloads(bad)
except AssertionError:print('RED actual result loop metadata rejected')
else:raise AssertionError('corruption not caught')
for mode in ['new','old']:
 exe=O/mode;cmd=['cc','-std=c11','-O2','-w','-DAUDIO_HOST','-DSKIN_HOST','-I',str(R/'viewer')]
 if mode=='old':cmd+=['-DBONUS_SOUND_OLD=1']
 cmd += [str(R/p) for p in ['tests/bonus/audio_host.c','viewer/bonus_audio.c','viewer/sound.c','viewer/audio.c']]+['-lm','-o',str(exe)]
 subprocess.run(cmd,check=True);run=subprocess.run([str(exe),str(bank)+'/'],capture_output=True,text=True);(O/(mode+'.txt')).write_text(run.stdout+run.stderr)
 assert (run.returncode==0)==(mode=='new'),run.stdout+run.stderr
 print(mode,run.returncode,run.stdout.strip())
(O/'sha.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [bank/'sfx.sab',bank/'music.sap',O/'new',O/'old']},indent=2))
print('PASS native audio + actual OLD red')
