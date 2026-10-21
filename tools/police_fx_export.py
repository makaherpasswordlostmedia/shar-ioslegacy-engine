#!/usr/bin/env python3
"""Мигалка cpolice: только родные AAX, суставы, CLR и scratch2.bmp с диска"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
from p3d import read,walk,string
from car_dump import skeleton,billboards,shaders
from frontend3d_export import anims
from char_export import load_images

def source():
 path=ROOT/'hit-and-run-web/source/game/art/cars/cpolice.p3d';r=read(path)
 comp=next(c for c in r.children if c.id==0x4512);_,p=string(comp.data);sk,_=string(comp.data,p)
 joints=skeleton(next(c for c in r.children if c.id==0x4500 and string(c.data)[0]==sk))
 bindings={}
 for c in walk(comp):
  if c.id==0x4516:
   n,p=string(c.data);_,j=struct.unpack_from('<II',c.data,p);bindings[n]=j
 animations=anims(r);rows=[]
 for g,sh,n,mode,pos,col,w,h,dist,zt,zw in billboards(r):
  if mode!='AAX' or not n.startswith('siren_'):continue
  a=animations['BQG_'+n];channels=a[3][n];fr,colors=channels['CLR'];assert len(fr)<=32
  assert a[0]=='BQG' and shaders(r)[sh][1]['BLMD']==2 and zt==1 and zw==0
  assert np.allclose(np.asarray(channels['TRAN'][1]),0) and len(channels['WDT'][0])==len(channels['HGT'][0])==1
  joint=joints[bindings[g]][3];position=(np.r_[pos,1.]@joint)[:3]
  position[2]*=-1 # геометрия CAR1 уже отражена по Z, та же система модели
  quad=next(c for c in walk(r) if c.id==0x17001 and string(c.data,4)[0]==n)
  _,p=string(quad.data,4);uv=struct.unpack_from('<8f',quad.data,p+4+12+4)
  rows.append(dict(name=n,pos=position.tolist(),w=w,h=h,dist=dist,uv=uv,frames=a[1],fps=a[2],keys=fr.tolist(),rgba=np.rint(colors*255).astype(int).tolist()))
 rows.sort(key=lambda x:x['name']);assert len(rows)==4
 w,h,pal,idx=load_images(r)['scratch2.bmp'];pixels=pal[np.asarray(idx).reshape(h,w)]
 return path,rows,pixels

def ff(x):
 s=format(float(x),'.9g');return s+('' if '.' in s or 'e' in s else '.0')+'f'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'viewer/police_fx_data.h');ap.add_argument('--json',type=Path);a=ap.parse_args()
 path,rows,pixels=source();frames={r['frames'] for r in rows};fps={r['fps'] for r in rows};assert len(frames)==len(fps)==1
 lines=['// Родной cpolice.p3d SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest(),'#ifndef POLICE_FX_DATA_H','#define POLICE_FX_DATA_H',f'#define PF_FRAME_COUNT {frames.pop()}',f'#define PF_FPS {ff(fps.pop())}',f'#define PF_TEX_W {pixels.shape[1]}',f'#define PF_TEX_H {pixels.shape[0]}',f'#define PF_FLARES {len(rows)}','static const PfDef pfDefs[PF_FLARES] = {']
 for r in rows:
  colors=[sum(int(v)<<(8*i) for i,v in enumerate(c)) for c in r['rgba']]
  lines.append('{"'+r['name']+'",{'+','.join(map(ff,r['pos']))+'},'+','.join(ff(r[k]) for k in ('w','h','dist'))+',{'+','.join(map(ff,r['uv']))+'},'+str(len(r['keys']))+',{'+','.join(map(str,r['keys']))+'},{'+','.join(hex(v)+'u' for v in colors)+'}},')
 lines+=['};','static const unsigned pfTexture[PF_TEX_W*PF_TEX_H] __attribute__((aligned(16))) = {']
 packed=np.asarray(pixels,np.uint8).tobytes();values=struct.unpack('<'+str(len(packed)//4)+'I',packed)
 for i in range(0,len(values),8):lines.append(','.join(hex(v)+'u' for v in values[i:i+8])+',')
 lines+=['};','#endif',''];a.out.write_text('\n'.join(lines))
 if a.json:a.json.write_text(json.dumps(dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),flares=rows,texture_sha256=hashlib.sha256(packed).hexdigest()),indent=2)+'\n')
 import audio_export as AE
 resources,cars,pos,_=AE.load_scripts();r=resources['siren'];p=pos['siren']
 assert r['loop'] and not r['stream'] and float(p['PlaybackProbability'])==1
 assert cars['cPolice']['HornClipName']==cars['cHears']['HornClipName']=='siren'
 (a.out.parent/'police_sound_data.h').write_text('// carsound.spt / positionalsettings.spt, trim применяется SAB ровно один раз\n#ifndef POLICE_SOUND_DATA_H\n#define POLICE_SOUND_DATA_H\n#define POLICE_SIREN_MIN '+ff(p['MinDistance'])+'\n#define POLICE_SIREN_MAX '+ff(p['MaxDistance'])+'\n#endif\n')
 print('native flares4/texture',pixels.shape,'->',a.out)
if __name__=='__main__':main()
