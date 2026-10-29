#!/usr/bin/env python3
"""Проба №426: добавить родную siren в существующий SAB, сохранив все старые id/сэмплы/EXT

Финальную сборку делает sound_export.py; этот узкий офлайн-адаптер не пересобирает SAP
"""
import argparse,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import audio_export as AE

def append_siren(old):
 h=list(struct.unpack_from('<10I',old,4));ver,nres,nfile,ncar,ro,vo,fo,co,do,ds=h
 assert old[:4]==b'SAB1' and ver==1 and do+ds<=len(old)
 resources=[old[ro+i*48:ro+(i+1)*48] for i in range(nres)]
 res,_,_,_=AE.load_scripts();r=res['siren']
 if any(x[:24].split(b'\0')[0]==b'siren' for x in resources):return old
 nvar=max(struct.unpack_from('<HH',x,24)[0]+struct.unpack_from('<HH',x,24)[1] for x in resources)
 assert nvar<65535 and nfile<65535
 variants=bytearray(old[vo:vo+2*nvar]);files=bytearray(old[fo:fo+32*nfile]);car=old[co:co+152*ncar]
 extOff,extSize=struct.unpack_from('<II',old,80);ext=old[extOff:extOff+extSize] if extSize else b''
 rs=AE.read_rsd(AE.game_path(r['files'][0]));assert len(r['files'])==1 and r['loop'] and not r['stream']
 seam,hist=AE.loop_points(rs);states=[v for pair in hist for v in pair]+[0,0]*(2-rs['ch'])
 resources.append(AE.pack_name('siren',24)+struct.pack('<HHfffII',nvar,1,r['trim'],*r['pitch'],1,AE.BUS['car']))
 variants+=struct.pack('<H',nfile);variants+=b'\0'*(-len(variants)%16)
 files+=struct.pack('<IIIIIHBB4h',ds,rs['nblk'],rs['nsamp'],seam['start'],seam['end'],rs['rate'],rs['ch'],0,*states)
 blob=old[do:do+ds]+rs['data'];blob+=b'\0'*(-len(blob)%64)
 rb=b''.join(resources);ro=96;vo=ro+len(rb);fo=vo+len(variants);co=fo+len(files);eo=(co+len(car)+15)&~15;do=(eo+len(ext)+63)&~63
 header=bytearray(old[:96]);struct.pack_into('<10I',header,4,ver,nres+1,nfile+1,ncar,ro,vo,fo,co,do,len(blob));struct.pack_into('<II',header,80,eo if ext else 0,len(ext))
 result=header+rb+variants+files+car;result+=b'\0'*(eo-len(result))+ext;result+=b'\0'*(do-len(result))+blob
 return bytes(result)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('bank',type=Path);ap.add_argument('out',type=Path);a=ap.parse_args()
 before=a.bank.read_bytes();after=append_siren(before);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(after);print('SAB',len(before),'->',len(after))
if __name__=='__main__':main()
