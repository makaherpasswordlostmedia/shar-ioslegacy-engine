"""Owned disc voice IDs for GagCheckCollCards/GagCheckMovie, original PS-ADPCM only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def voices():
 import sys
 sys.path.insert(0,str(ROOT/'tools/missions'))
 from compile import conversation_index
 idx=conversation_index();out=[]
 for name in ('rewardsuccess','rewardintro','rewardfail','aztec1','aztec2','aztec3','aztec4'):
  rows=idx.get((name,0,''));assert rows and len(rows)==1,(name,rows)
  line,kind,actor,file=rows[0];assert line==1 and kind=='convinit'
  out.append(dict(conv=name,actor=actor,file=file))
 return out

def streams(level):
 if level!=3:return []
 from sound_export import voice_track_name
 return [(voice_track_name(v['file']),str(ROOT/'hit-and-run-web/source/game'/v['file'])) for v in voices()]
