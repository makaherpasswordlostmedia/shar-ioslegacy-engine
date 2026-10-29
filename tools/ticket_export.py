#!/usr/bin/env python3
"""Two authored L3 conditional gag routes plus owned conversation file IDs -> TKT1."""
import argparse,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hit-and-run-web/tools'));sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tools/missions'))
import mfk
from ticket_audio import voices
from ticket_source import facts

def routes():
 calls=mfk.parse((ROOT/'hit-and-run-web/source/game/scripts/missions/level03/level.mfk').read_text())[0]
 result=[];gag=-1
 for c in calls:
  if c.op=='GagBegin':gag+=1
  if c.op=='GagCheckCollCards':
   npc,pc,yes,intro,no=map(str,c.args);result.append(dict(kind=1,gag=gag,pc=pc,npc=npc,yes=yes,intro=intro,no=no,movie=''))
  if c.op=='GagCheckMovie':
   npc,pc,movie,no=map(str,c.args);result.append(dict(kind=2,gag=gag,pc=pc,npc=npc,yes='',intro='',no=no,movie=Path(movie).stem))
 assert len(result)==2
 return result

def fixed(s,n):b=s.encode();assert len(b)<n;return b+b'\0'*(n-len(b))
def export(out):
 facts();rs=routes();vs=voices();b=bytearray(b'TKT1'+struct.pack('<III',1,len(rs),len(vs)))
 for r in rs:b+=struct.pack('<II',r['kind'],r['gag'])+b''.join(fixed(r[k],32) for k in ('pc','npc','yes','intro','no'))+fixed(r['movie'],16)
 for v in vs:b+=fixed(v['conv'],32)+fixed(v['actor'],8)+fixed(v['file'],128)
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b);return rs,vs
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args();rs,vs=export(a.out);print('TKT1',len(rs),'routes',len(vs),'original voices',a.out)
