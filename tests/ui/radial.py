#!/usr/bin/env python3
"""Rasterise actual PSP ring fan vertices with the packed texture; no emulator claims."""
import argparse
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--negative', action='store_true')
args = ap.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
subprocess.run(['cc','-std=c99','-I',str(ROOT/'viewer'),str(Path(__file__).with_suffix('.c')),'-lm','-o',str(args.out/'radial')],check=True)
lines = subprocess.check_output([str(args.out/'radial')],text=True).splitlines()
fans = {}
for line in lines:
    n = line.split(); fans[int(n[0])] = np.array(list(map(float,n[2:]))).reshape(-1,2)
b = (ROOT/'build/ui.shr').read_bytes()
ni,oi = struct.unpack_from('<II',b,16)
ot = struct.unpack_from('<I',b,12)[0]; oslot = struct.unpack_from('<I',b,68)[0]
item = next(b[oi+i*64:oi+(i+1)*64] for i in range(ni) if b[oi+i*64]==2 and b[oi+i*64+2]==27)
first = struct.unpack_from('<H',item,28)[0]
ti,u,v,w,h,x,y,_ = struct.unpack_from('<5H3h',b,oslot+first*16)
psm,flags,tw,th,op,oc,nc,bw,rows,_ = struct.unpack_from('<4H6I',b,ot+ti*32)
assert psm==5 and flags&1 and w==h and x>350 and y>150
raw=np.frombuffer(b,np.uint8,count=bw*rows,offset=op)
idx=raw.reshape(rows//8,bw//16,8,16).transpose(0,2,1,3).reshape(rows,bw)
pal=np.frombuffer(b,np.uint8,count=nc*4,offset=oc).reshape(nc,4)
ring=Image.fromarray(pal[idx[v:v+h,u:u+w]],'RGBA')
renders={}
for val,points in fans.items():
    # Negative control recreates the old 12.5% quantisation: 3% and 6% must no longer coincide.
    if args.negative and val in (30,60): points=fans[125]
    mask=Image.new('L',(w,h),0)
    if len(points): ImageDraw.Draw(mask).polygon([tuple(p*[w,h]) for p in points],fill=255)
    rgba=np.array(ring);rgba[:,:,3]=np.minimum(rgba[:,:,3],np.array(mask))
    renders[val]=rgba
counts=[int((renders[k][:,:,3]>128).sum()) for k in fans]
assert counts[0]==0 and all(a<b for a,b in zip(counts,counts[1:])), counts
assert renders[250][:h//2,w//2:,3].sum()>0 and renders[250][h//2+2:,:w//2-2,3].sum()==0
assert all(a[h//2,w//2,3]==0 for a in renders.values()), 'radar interior overwritten'
sheet=Image.new('RGBA',(400,240),(30,36,43,255));d=ImageDraw.Draw(sheet)
for i,(val,rgba) in enumerate(renders.items()):
    dx=(i%4)*100+7;dy=(i//4)*120+20
    sheet.alpha_composite(Image.fromarray(rgba,'RGBA'),(dx,dy));d.text((dx,dy-16),f'{val/10:g}%',fill='white')
sheet.save(args.out/'ring-progress.png')
print(f'PASS: clockwise continuous coverage {counts}; original ring at ({x},{y}) {w}x{h}; radar centre clear')
