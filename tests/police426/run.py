#!/usr/bin/env python3
"""Диск -> настоящий geometry/sound/mixer; OLD и реальные порчи банка красные"""
import argparse,hashlib,math,os,re,struct,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT)
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
from p3d import read,walk,string
from car_dump import skeleton
from frontend3d_export import anims
from char_export import load_images
import audio_export as AE
OUT=ROOT/'build/police426';OUT.mkdir(exist_ok=True)
ap=argparse.ArgumentParser()
ap.add_argument('--reference-old',type=Path,default=ROOT/'build/ship_stage/audio/sfx.sab')
ap.add_argument('--reference-new',type=Path,default=OUT/'sfx.sab')
args=ap.parse_args()
def run(args):
 r=subprocess.run(list(map(str,args)),capture_output=True,text=True)
 if r.returncode:raise RuntimeError(f'{args}: rc{r.returncode}\n{r.stdout}\n{r.stderr}')
 return r.stdout
def compile(name,files,flags=()):
 out=OUT/name
 run(['cc','-std=c11','-O2','-w','-ffunction-sections','-fdata-sections','-Wl,-dead_strip','-Iviewer',*flags,*files,'-lm','-o',out]);return out
# Raw P3D nodes, separately bind the actual billboard groups to articulated joints
r=read(ROOT/'hit-and-run-web/source/game/art/cars/cpolice.p3d')
sk=skeleton(next(c for c in r.children if c.id==0x4500))
bind={}
for c in walk(r):
 if c.id==0x4516:
  n,p=string(c.data);bind[n]=struct.unpack_from('<II',c.data,p)[1]
rows=[];aa=anims(r)
for g in walk(r):
 if g.id!=0x17002:continue
 gn,p=string(g.data,4);shader,p=string(g.data,p)
 for q in g.children:
  if q.id!=0x17001:continue
  n,p=string(q.data,4)
  if not n.startswith('siren_') or q.data[p:p+4]!=b'AAX\0':continue
  xyz=np.r_[struct.unpack_from('<3f',q.data,p+4),1.]@sk[bind[gn]][3]
  # q=identity: CAR1 renderer maps reflected model to world (-X,+Y,-Z)
  xyz=xyz[:3]*[-1,1,1]
  uv=np.asarray(struct.unpack_from('<8f',q.data,p+20)).reshape(4,2)
  w,h,dist=struct.unpack_from('<3f',q.data,p+52)
  kind,frames,fps,ch=aa['BQG_'+n];keys,rgba=ch[n]['CLR']
  rows.append((n,xyz,uv,w,h,dist,frames,fps,keys,np.rint(rgba*255)))
rows.sort(key=lambda x:x[0]);assert len(rows)==4
w,h,pal,idx=load_images(r)['scratch2.bmp'];native_texture=pal[np.asarray(idx).reshape(h,w)].astype(np.uint8).tobytes()
def judge(text,texture):
 try:
  assert texture==native_texture
  fs={int(i):int(n) for i,n in re.findall(r'^F (\d+) (\d+)$',text,re.M)};assert len(fs)==84
  actual={}
  for line in text.splitlines():
   if not line.startswith('Q '):continue
   parts=line.split();actual[(int(parts[1]),int(parts[2]))]=(int(parts[3],16),np.asarray(list(map(float,parts[4:]))).reshape(6,5))
  expected=0
  for i in range(84):
   count=0
   for j,(n,p,uv,w,h,dist,frames,fps,keys,rgba) in enumerate(rows):
    frame=(i/2)%frames;k=max(k for k,v in enumerate(keys) if v<=frame)
    color=rgba[k] if k+1==len(keys) else rgba[k]+(rgba[k+1]-rgba[k])*(frame-keys[k])/(keys[k+1]-keys[k])
    col=sum(math.floor(float(v)+.5)<<(8*c) for c,v in enumerate(color))
    if not col&0xffffff:continue
    count+=1;expected+=1;ac,verts=actual[(i,j)];assert ac==col
    norm=np.asarray([0,3,10])-p;norm/=np.linalg.norm(norm)
    right=np.cross([0,1,0],norm);right/=np.linalg.norm(right);up=np.cross(norm,right)
    points=np.asarray([p+norm*dist+sx*w*.5*right+sy*h*.5*up for sx,sy in [(-1,1),(1,1),(1,-1),(-1,-1)]])
    order=[0,1,2,0,2,3]
    assert np.array_equal(verts[:,:2],uv[order])
    assert np.max(np.abs(verts[:,2:]-points[order]))<2e-6 # f32 geometry arithmetic, NOT visual tolerance
   assert fs[i]==count
  assert len(actual)==expected
  return True
 except (AssertionError,KeyError):return False
for side,flags in [('new',[]),('old',['-DPOLICE_FX_OLD=1'])]:
 exe=compile('flare-'+side,['tests/police426/flare.c','viewer/car.c','viewer/col.c'],['-DSKIN_HOST',*flags])
 tex=OUT/(side+'.rgba');log=run([exe,tex]);(OUT/(side+'-flare.log')).write_text(log)
 ok=judge(log,tex.read_bytes());print('FLARE',side,ok);assert ok==(side=='new')
 if side=='new':
  corrupted=bytearray(tex.read_bytes());corrupted[3]^=255;assert not judge(log,corrupted);print('FLARE real texture corruption rejected')
# Runtime sound.c pool: actual old branch must fail same lifecycle conditions
resources,cars,pos,_=AE.load_scripts();s=resources['siren'];p=pos['siren'];assert s['loop'] and not s['stream']
assert cars['cPolice']['HornClipName']==cars['cHears']['HornClipName']=='siren'
for side,flags in [('new',[]),('old',['-DPOLICE_SIREN_OLD=1'])]:
 exe=compile('siren-'+side,['tests/police426/siren.c'],['-DSKIN_HOST',*flags]);rr=subprocess.run([exe],capture_output=True,text=True)
 (OUT/(side+'-siren.log')).write_text(rr.stdout)
 assert rr.returncode==(side=='old')
 if side=='new':
  plays=re.findall(r'^PLAY (.+)$',rr.stdout,re.M);assert len(plays)==2
  for line in plays:
   fields=list(map(float,line.split()));assert fields[1]==1 and fields[-2:]==[float(p['MinDistance']),float(p['MaxDistance'])]
 print('SIREN',side,'rc',rr.returncode)
# Bank semantics: every old resource, variant, file/car/EXT/sample stays byte exact
def bank(b):
 h=struct.unpack_from('<10I',b,4);v,nr,nf,nc,ro,vo,fo,co,do,ds=h
 rs=[b[ro+48*i:ro+48*(i+1)] for i in range(nr)];nv=max(sum(struct.unpack_from('<HH',r,24)) for r in rs)
 eo,es=struct.unpack_from('<II',b,80)
 return rs,b[vo:vo+nv*2],b[fo:fo+nf*32],b[co:co+nc*152],b[eo:eo+es],b[do:do+ds]
old=args.reference_old.read_bytes();new=args.reference_new.read_bytes();a,b=bank(old),bank(new)
assert b[0][:-1]==a[0] and b[1][:len(a[1])]==a[1] and b[2][:-32]==a[2] and b[3:5]==a[3:5] and b[5][:len(a[5])]==a[5]
res=b[0][-1];nv,nvar,trim,lo,hi,flags,bus=struct.unpack_from('<HHfffII',res,24)
assert res[:24].split(b'\0')[0]==b'siren' and nvar==1 and abs(trim-s['trim'])<1e-7 and (lo,hi)==s['pitch'] and flags==1 and bus==AE.BUS['car']
rsd=AE.read_rsd(AE.game_path(s['files'][0]));off,nblk,nsamp,ls,le,rate,ch,_,*hist=struct.unpack('<IIIIIHBB4h',b[2][-32:]);lp,lh=AE.loop_points(rsd)
assert b[5][off:off+len(rsd['data'])]==rsd['data'] and (nblk,nsamp,rate,ch)==tuple(rsd[k] for k in ['nblk','nsamp','rate','ch'])
assert (ls,le)==(lp['start'],lp['end']);assert off==len(a[5]);print('BANK old semantics unchanged/native RSD SHA',hashlib.sha256(rsd['data']).hexdigest())
# The release bank includes other accepted audio additions. Validate its actual
# siren by named resource and referenced file, independently of historical IDs.
new=(ROOT/'build/ship_stage/audio/sfx.sab').read_bytes()
_,nr,nf,nc,ro,vo,fo,co,do,ds=struct.unpack_from('<10I',new,4)
ri=next(i for i in range(nr) if new[ro+i*48:ro+i*48+24].split(b'\0')[0]==b'siren')
nv,nvar,trim,lo,hi,flags,bus=struct.unpack_from('<HHfffII',new,ro+ri*48+24)
assert nvar==1 and abs(trim-s['trim'])<1e-7 and (lo,hi)==s['pitch'] and flags==1 and bus==AE.BUS['car']
fi=struct.unpack_from('<H',new,vo+nv*2)[0];assert fi<nf
off,nblk,nsamp,ls,le,rate,ch,_,*hist=struct.unpack_from('<IIIIIHBB4h',new,fo+fi*32)
assert new[do+off:do+off+len(rsd['data'])]==rsd['data']
assert (nblk,nsamp,rate,ch)==tuple(rsd[k] for k in ['nblk','nsamp','rate','ch']) and (ls,le)==(lp['start'],lp['end'])
print('BANK actual staged native siren SHA',hashlib.sha256(new).hexdigest())
mix=compile('mix',['tests/police426/mix.c','viewer/audio.c'],['-DAUDIO_HOST'])
def mixbank(label,data,dist):
 d=OUT/label;d.mkdir(exist_ok=True);(d/'sfx.sab').write_bytes(data)
 rr=subprocess.run([mix,str(d)+'/',str(dist)],capture_output=True,text=True);(OUT/(label+'-mix.log')).write_text(rr.stdout+rr.stderr)
 return rr
energies=[]
for dist in (0,80,165,250):
 rr=mixbank('mix'+str(dist),new,dist);assert rr.returncode==0
 e=list(map(float,re.search(r'^PCM (.+)$',rr.stdout,re.M)[1].split()));energies.append(e)
 assert all(x>0.001 for x in e) if dist<250 else all(x==0 for x in e)
print('PCM loop six seconds RMS',energies)
assert energies[0]==energies[1]
assert all(abs(x/y-.25)<.001 for x,y in zip(energies[2],energies[0])) # existing port mixer squared attenuation, native bounds
rr=mixbank('missing',old,0);assert rr.returncode==1
bad=bytearray(new);struct.pack_into('<I',bad,ro+ri*48+40,0)
rr=mixbank('no-loop',bad,0);assert rr.returncode==1;print('PCM missing clip / actual nonloop bank rejected')
# Re-export staleness check independent of committed headers
generated=OUT/'police_fx_data.h';run([sys.executable,'tools/police_fx_export.py','--out',generated])
for name in ['police_fx_data.h','police_sound_data.h']:assert (OUT/name).read_bytes()==(ROOT/'viewer'/name).read_bytes()
print('PASS source/geometry/animation/texture/lifecycle/bank/real mixer; no GPU or PSP claim')
