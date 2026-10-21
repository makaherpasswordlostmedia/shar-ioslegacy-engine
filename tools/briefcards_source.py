#!/usr/bin/env python3
"""Facts extracted from Robert's SLES_518.97, not leaked source.
Original 0x19e378..0x19e770 compares b_<giver>, then loads its briefing P3D.
We validate the actual pointer-building instructions; string adjacency alone is not evidence.
"""
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DISC=ROOT/'hit-and-run-web/source/disc/SLES_518.97'
def builtin_mappings():
 b=DISC.read_bytes();phoff=struct.unpack_from('<I',b,28)[0];size,n=struct.unpack_from('<HH',b,42)
 seg=[]
 for i in range(n):
  typ,off,va,_,sz,*_=struct.unpack_from('<8I',b,phoff+i*size)
  if typ==1:seg.append((off,va,sz))
 def fileoff(va):return next(off+va-base for off,base,sz in seg if base<=va<base+sz)
 def word(va):return struct.unpack_from('<I',b,fileoff(va))[0]
 def ptr(va,reg):
  w=word(va);assert w>>16==((9<<10)|(reg<<5)|reg),hex(va)
  hi=0x46
  lo=w&65535;lo=lo-65536 if lo>=32768 else lo
  p=fileoff((hi<<16)+lo);return b[p:b.index(0,p)].decode()
 # These are factual instruction addresses on the owned PAL executable.
 low_name=[0x19e39c]+[0x19e3d4+64*i for i in range(13)]+[0x19e728]
 low_path=[0x19e3c8]+[0x19e408+64*i for i in range(12)]+[0x19e704,0x19e75c]
 out={}
 for np,pp in zip(low_name,low_path):
  # Each return/load path follows the comparison of the NPC constructed at np.
  assert word(np-4)==0x0c0c8212 or word(np+4)==0x0c0c8212
  assert word(pp-4)==0x10000000|((0x19e708-(pp-4+4))//4&0xffff) or pp in (0x19e704,0x19e75c)
  name=ptr(np,5);path=ptr(pp,4)
  assert name.startswith('b_') and path.startswith('art/frontend/dynaload/images/mis')
  out[name[2:]]=path.lower()
 return out

def builtin_paths():
 # PS/HW are also loaded by original failure/tutorial flows; all six misXX assets exist on the disc.
 return sorted(set(builtin_mappings().values())|{str(p.relative_to(ROOT/'hit-and-run-web/source/game')).lower() for p in (ROOT/'hit-and-run-web/source/game/art/frontend/dynaload/images').glob('misxx_*.p3d')})
if __name__=='__main__':
 for npc,path in builtin_mappings().items():print(npc,path)
