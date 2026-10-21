#!/usr/bin/env python3
"""Production exporter + byte-exact disc blocks, actual stream lifecycle, OLD red."""
import json,os,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import audio_export as A, sound_export as S
OUT=ROOT/'build/stream-overlay';OUT.mkdir(parents=True,exist_ok=True)
def main():
 names=['ship','icecream','IStruck','nuctruck','votetruc','gramR_v'];res,cars,*_=A.load_scripts()
 overlays=S.car_stream_overlays(names,res,cars);assert len(overlays)==7
 os.environ['CAR_STREAM_OLD']='1';assert not S.car_stream_overlays(names,res,cars);del os.environ['CAR_STREAM_OLD']
 fixture=A.game_path(res['ship_overlay']['files'][0])
 ext=b'SXT1'+struct.pack('<I',0)
 pack=OUT/'pack'
 report=A.build_pack(str(pack),'famil_v',[],[('test_music',fixture,True,None)],[('test_amb',fixture)],[('test_dialog',fixture)],ext=ext,pos_sel=[('test_pos',fixture)],extra_cars=names,car_sel=overlays,quiet=True)
 sap=(pack/'music.sap').read_bytes();sab=(pack/'sfx.sab').read_bytes();nt,to=struct.unpack_from('<II',sap,8);assert nt==11
 for i,(car,name,path,trim) in enumerate(overlays):
  o=to+64*(4+i);track=sap[o:o+28].split(b'\0')[0].decode();off,nb,ns,ls,le,rate,ch,flags,nxt,bus=struct.unpack_from('<IIIIIHBBhh',sap,o+28)
  rs=A.read_rsd(path);raw=rs['data'];stereo=raw if rs['ch']==2 else b''.join(raw[k:k+16]*2 for k in range(0,len(raw),16))
  assert track==name and bus==4 and flags&1 and nxt==-1 and rate==rs['rate'] and ch==2
  assert sap[off:off+len(stereo)]==stereo,'source ADPCM changed'
 eo,es=struct.unpack_from('<II',sab,80);ext=sab[eo:eo+es];ns,=struct.unpack_from('<I',ext,4);sections={ext[8+16*i:12+16*i]:struct.unpack_from('<III',ext,12+16*i) for i in range(ns)}
 so,count,stride=sections[b'COVS'];vo,nvar,vstride=sections[b'COVF'];assert count==7 and stride==4 and nvar==7 and vstride==8
 for k,car in enumerate(['famil_v',*names]):
  first,n=struct.unpack_from('<HH',ext,so+4*k)
  expected=[(4+i,trim) for i,(owner,_,_,trim) in enumerate(overlays) if owner==car]
  assert n==len(expected)
  for j,(tid,trim) in enumerate(expected):
   actual,pad,gain=struct.unpack_from('<hhf',ext,vo+8*(first+j));assert actual==tid and pad==0 and abs(gain-trim)<1e-6
 first,n=struct.unpack_from('<HH',ext,so+4*5);assert n==3,'two silent vote variants lost'
 assert [struct.unpack_from('<h',ext,vo+8*(first+i))[0] for i in range(n)]==[8,9,10]
 outputs={}
 for old in (False,True):
  binary=OUT/('old' if old else 'green');cmd=['cc','-O2','-DAUDIO_HOST','-Iviewer','tests/hover/stream_overlay.c','-lm','-o',str(binary)]
  if old:cmd.insert(2,'-DCAR_STREAM_OLD=1')
  subprocess.run(cmd,cwd=ROOT,check=True);r=subprocess.run([str(binary),str(pack)+'/'],capture_output=True,text=True)
  (OUT/('old.txt' if old else 'green.txt')).write_text(r.stdout+r.stderr);print(r.stdout)
  outputs[old]=r.stdout
  assert (r.returncode==1 and 'FAIL stream overlay starts' in r.stdout) if old else r.returncode==0
 for name,flags in [('copy',['-DMIX_JOB_COPY=1']),('kernel',['-DMIX_JOB_COPY=2']),('broken',['-DMIX_JOB_COPY=1','-DMIX_JOB_RED=1'])]:
  binary=OUT/name;subprocess.run(['cc','-O2','-DAUDIO_HOST',*flags,'-Iviewer','tests/hover/stream_overlay.c','-lm','-o',str(binary)],cwd=ROOT,check=True)
  r=subprocess.run([str(binary),str(pack)+'/'],capture_output=True,text=True);(OUT/(name+'.txt')).write_text(r.stdout+r.stderr)
  if name=='broken':assert r.returncode==1 or r.stdout!=outputs[False],'broken copy escaped'
  else:assert r.returncode==0 and r.stdout==outputs[False],('shared DSP copy differs',name)
 oldpack=OUT/'oldpack'
 A.build_pack(str(oldpack),'famil_v',[],[('test_music',fixture,True,None)],[('test_amb',fixture)],[('test_dialog',fixture)],ext=b'SXT1'+struct.pack('<I',0),pos_sel=[('test_pos',fixture)],extra_cars=names,quiet=True)
 r=subprocess.run([str(OUT/'green'),str(oldpack)+'/'],capture_output=True,text=True)
 (OUT/'oldpack.txt').write_text(r.stdout+r.stderr);assert r.returncode==1 and 'FAIL stream overlay starts' in r.stdout
 (OUT/'result.json').write_text(json.dumps(dict(ok=True,streams=len(overlays),source_blocks_exact=True,old_caught=True,resident_bytes=report['resident_audio_bytes'],sap_bytes=report['sap_bytes']),indent=2)+'\n')
 print('PASS source7/lifecycle5/resident neighbour; OLD caught')
if __name__=='__main__':main()
