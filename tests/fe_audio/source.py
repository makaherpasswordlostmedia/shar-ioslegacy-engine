#!/usr/bin/env python3
"""Independent raw NIS/SLES/observer/SAP oracle; no new exporter import."""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];GAME=ROOT/'hit-and-run-web/source/game'
ap=argparse.ArgumentParser();ap.add_argument('packet',type=Path);ap.add_argument('--raw',type=Path);ap.add_argument('--native-log',type=Path);ap.add_argument('--observer',type=Path,default=ROOT.parent/'shar-psp-ps2-w/knowledge/facts/ps2-main-menu-runtime.yaml');a=ap.parse_args()
bad=0
def ck(label,ok,detail=''):
 global bad;bad+=not ok;print('CHECK',label,'PASS' if ok else 'FAIL',detail)
source=(GAME/'sound/scripts/nis.spt').read_text();resources={}
for name,body in re.findall(r'create\s+daSoundResourceData\s+named\s+(FE_Gag_\w+)\s*\{([^}]+)\}',source):
 f=re.search(r'AddFilename\s*\(\s*"([^"]+)"\s+([\d.]+)',body);trim=re.search(r'SetTrim\s*\(\s*([\d.]+)',body)
 resources[name]=(f[1],float(trim[1]) if trim else 1.,trim is None)
ck('raw_NIS_resources12',len(resources)==12);ck('Homer_dispatcher_not_NIS_resource','FE_Gag_Homer' not in resources)
obs=json.loads(a.observer.read_text());keys=obs['sound_keys']+obs['homer_sound_keys'];ck('observed_runtime_keys13',len(keys)==13)
def h31(s):
 h=0
 for b in s.encode():h=(h*31+b)&0xffffffff
 return h
for row in keys:ck('runtime_key_'+row['name'],h31(row['name'])==int(row['key'],16) and h31(row['name'].lower())!=int(row['key'],16))
ck('keys_equal_NIS_plus_dispatcher',{r['name'] for r in keys}==set(resources)|{'FE_Gag_Homer'})
elf=(ROOT/'hit-and-run-web/source/disc/SLES_518.97').read_bytes();phoff=struct.unpack_from('<I',elf,28)[0];phsz,phn=struct.unpack_from('<HH',elf,42)
def va(addr,n):
 for i in range(phn):
  typ,off,v,_,sz=struct.unpack_from('<5I',elf,phoff+i*phsz)
  if typ==1 and v<=addr and addr+n<=v+sz:return elf[off+addr-v:off+addr-v+n]
 raise ValueError('ELF unmapped '+hex(addr))
text=va(0x1b9088,0x4ac);words=struct.unpack('<'+str(len(text)//4)+'I',text)
ck('SLES_event180_181_in_MainMenu_Update',0x240500b4 in words and 0x240500b5 in words)
ck('SLES_exact_disc_sha256',hashlib.sha256(elf).hexdigest()=='e936793df537c2764fae6908d52bbbcbc41606080855f1a26751ffb28bfbfa47')
b=a.packet.read_bytes();magic,version,n,off=struct.unpack_from('<4sIII',b);ck('actual_SAP1_header',magic==b'SAP1' and version==1 and n==12 and off==64)
names=[]
for i in range(n):
 row=b[off+i*64:off+(i+1)*64];name=row[:28].split(b'\0')[0].decode();names.append(name);r=struct.unpack_from('<IIIIIHBBhh4h',row,28)
 if name not in resources:ck('unknown_track_'+name,False);continue
 rel,trim,implicit=resources[name];directory=GAME/Path(rel).parent;path=next(p for p in directory.iterdir() if p.name.lower()==Path(rel).name.lower());src=path.read_bytes();ch,bits,rate=struct.unpack_from('<III',src,8);data=src[2048:];blocks=len(data)//(16*ch);data=data[:blocks*16*ch];widen=b''.join(data[k:k+16]*2 for k in range(0,len(data),16)) if ch==1 else data
 ck(name+'_PS_ADPCM_original',b[r[0]:r[0]+r[1]*32]==widen)
 ck(name+'_authored_metadata',src[:8]==b'RSD4VAG ' and r[1]==blocks and r[2]==blocks*28 and r[5]==rate and r[6:10]==(2,0,-1,2) and trim==1.,'trim implicit default1' if implicit else 'explicit trim1')
 if a.raw:
  actual=np.fromfile(a.raw/(name+'.raw'),'<i2').reshape(-1,2)
  p=subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-f','s16le','-'],capture_output=True,check=True)
  pcm=np.frombuffer(p.stdout,'<i2').reshape(-1,ch);expected=np.repeat(pcm,2,axis=1) if ch==1 else pcm
  count=min(len(actual),len(expected));difference=int(np.count_nonzero(actual[:count]!=expected[:count]));ck(name+'_real_backend_decode',len(actual)>=len(expected) and not difference,f'sourceframes={len(expected)} actualframes={len(actual)} mismatched_samples={difference}')
ck('SAP_names_exact',set(names)==set(resources) and len(set(names))==12)
if a.native_log:
 # The expected runtime mapping comes from the original observer, not either
 # the new exporter list or feAudioName(). A matching producer permutation fails.
 expected={(row['index'],-1):row['name'] for row in obs['sound_keys'] if row['index']}
 expected.update({(0,row['segment']):row['name'] for row in obs['homer_sound_keys']})
 actual=re.findall(r'^CLIP (\S+) index=(-?\d+) seg=(-?\d+) ',a.native_log.read_text(),re.M)
 routes=[]
 for i,(name,index,segment) in enumerate(actual):
  pair=(int(index),int(segment));routes.append(pair);ck('runtime_route'+str(i)+'_matches_original_observer',expected.get(pair)==name,f'index={index} segment={segment} actual={name} original={expected.get(pair)}')
 ck('runtime_all12_original_routes_present',set(routes)==set(expected))
 ck('runtime_repeat_original_Nick_route',routes.count((5,-1))==2)
print('RESULT','FAIL' if bad else 'PASS',f'failures={bad}');raise SystemExit(bool(bad))
