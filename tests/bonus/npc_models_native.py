#!/usr/bin/env python3
"""Measured default Lisa/b01 Vehicle bindings and actual MCR loads, OLD red."""
import sys
from pathlib import Path
import unlock_emu as U
U.OUT=U.ROOT/'build/gates/bonus_npc';U.OUT.mkdir(parents=True,exist_ok=True)
red='--red' in sys.argv;args=[a for a in sys.argv[1:] if a!='--red']
scen='flag menu\nflag bonusopen\nflag bonusshots 1\nflag bonusquit 1\nwait 2\npress left\nwait .6\npress cross\nwait 2\nflag bonusgo\nwait 15\nend\n'
d,bad=U.run('old' if red else 'green',Path(args[0]).resolve(),scen,timeout=240)
log=U.lines(d);start=[U.kv(l) for l in log if l.startswith('BONUS ev=start track=1 ')]
loaded={l.split()[2].lower() for l in log if l.startswith('MCR load ')}
want={'famil_v','pickupa','climo','otto_v'}
ok=bool(start) and start[0].get('car')=='famil_v' and start[0].get('ai')=='pickupA,cLimo,otto_v' and want<=loaded
print('native:',d,'start:',start,'MCR loaded:',sorted(loaded),'runner:',bad or 'END/errors0')
if red:
 old={'famil_v','bart_v','homer_v','marge_v'}
 caught=not ok and bool(start) and start[0].get('ai')=='bart_v,homer_v,marge_v' and old<=loaded and not bad
 print('RED CAUGHT' if caught else 'RED NOT CAUGHT');sys.exit(0 if caught else 1)
print('PASS typed PS2 models + actual MCR loads' if ok and not bad else 'FAIL native NPC models');sys.exit(0 if ok and not bad else 1)
