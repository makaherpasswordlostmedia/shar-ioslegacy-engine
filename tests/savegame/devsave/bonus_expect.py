#!/usr/bin/env python3
"""DEV contract from Rob 350 plus independent personal-disc AddBonusMission/GagSetCoins."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from missions.mfk import parse
G = ROOT/'hit-and-run-web/source/game/scripts/missions'
for level in range(1,8):
    base = G/f'level0{level}'
    calls,_=parse((base/'level.mfk').read_text(errors='replace'))
    bonus=[str(c.args[0]) for c in calls if c.op=='AddBonusMission' and (base/f'{c.args[0]}i.mfk').is_file()]
    coded=[str(c.args[0]) for c in calls if c.op=='AddBonusMission' and not (base/f'{c.args[0]}i.mfk').is_file()]
    if coded: print(f'NOT_COVERED L{level} engine-coded bonus: {coded}', file=sys.stderr)
    gi=-1; mask=0
    for c in calls:
        if c.op=='GagBegin': gi+=1
        if c.op=='GagSetCoins' and int(c.args[0])>0: mask |= 1<<gi
    init,_=parse((base/'leveli.mfk').read_text(errors='replace'))
    wasps=sum(c.op=='AddSpawnPointByLocatorScript' and str(c.args[1]).lower()=='beecamera' for c in init)
    print(level,','.join(bonus),hex(mask),wasps,sep='\t')
