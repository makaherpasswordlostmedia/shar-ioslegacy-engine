#!/usr/bin/env python3
"""Read UIP1 texture slots without importing the exporter or changing its files."""
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]


def extract(out, pack=None, layout=None):
    pack=pack or ROOT/'build/ui.shr'; layout=layout or ROOT/'build/ui/layout.json'
    b=pack.read_bytes(); j=json.loads(layout.read_text())
    if len(b)<128 or b[:4]!=b'UIP1': raise ValueError('not UIP1')
    ntex,ot,ni,oi,ns,os=struct.unpack_from('<6I',b,8)
    nslot,osl=struct.unpack_from('<2I',b,64)
    if max(ot+32*ntex,oi+64*ni,os+16*ns,osl+16*nslot)>len(b): raise ValueError('UIP bounds')
    tex=[]
    for i in range(ntex):
        psm,flags,w,h,op,oc,nc,bw,rows,_=struct.unpack_from('<4H6I',b,ot+32*i)
        if psm not in (4,5): raise ValueError('unsupported PSM')
        wb=bw//2 if psm==4 else bw
        if op+wb*rows>len(b) or oc+nc*4>len(b): raise ValueError('texture bounds')
        a=np.frombuffer(b[op:op+wb*rows],np.uint8)
        if flags&1: a=a.reshape(rows//8,wb//16,8,16).transpose(0,2,1,3).reshape(rows,wb)
        else:a=a.reshape(rows,wb)
        if psm==4:a=np.stack([a&15,a>>4],axis=-1).reshape(rows,bw)
        cl=np.frombuffer(b[oc:oc+nc*4],np.uint8).reshape(nc,4)
        tex.append(cl[a])
    out.mkdir(parents=True,exist_ok=True); records=[]
    for si,(screen,items) in enumerate(j['screens'].items()):
        if si>=ns:raise ValueError('layout/pack screen mismatch')
        first,count,_,_=struct.unpack_from('<4I',b,os+16*si)
        if len(items)!=count:raise ValueError('layout/pack item mismatch')
        for k,item in enumerate(items):
            if screen!='hud' or item['name']!='ActionButton':continue
            off=oi+64*(first+k); typ=b[off]
            if typ!=2:raise ValueError('ActionButton must be an image')
            f,c=struct.unpack_from('<2H',b,off+28)
            if c<1 or f>=nslot:raise ValueError('invalid image slot')
            ti,u,v,w,h,x,y,pad=struct.unpack_from('<5H3h',b,osl+16*f)
            im=tex[ti][v:v+h,u:u+w]
            if im.shape[:2]!=(h,w):raise ValueError('slot crop bounds')
            name='action.png';Image.fromarray(im,'RGBA').save(out/name)
            records.append(dict(name='action',image=name,source='ui.shr',rect_psp=item['dst'],size=[w,h]))
    if not records:raise ValueError('no ActionButton in current UI pack')
    (out/'templates.json').write_text(json.dumps(dict(pack_sha256=hashlib.sha256(b).hexdigest(),
        layout_sha256=hashlib.sha256(layout.read_bytes()).hexdigest(),templates=records),indent=2)+'\n')
    return records


if __name__=='__main__':print(extract(ROOT/'build/ps2ref/templates'))
