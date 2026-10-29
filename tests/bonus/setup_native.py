#!/usr/bin/env python3
"""PS2 selection order/defaults/range and two confirmations, actual OLD red."""
import sys
from pathlib import Path
import unlock_emu as U
U.OUT=U.ROOT/'build/gates/bonus_setup'; U.OUT.mkdir(parents=True,exist_ok=True)
red='--red' in sys.argv
args=[a for a in sys.argv[1:] if a!='--red']
d,bad=U.run('old' if red else 'green',Path(args[0]).resolve(),(U.HERE/'setup_scenario.txt').read_text(),timeout=240)
log=U.lines(d); ev=[U.kv(l) for l in log if l.startswith('BONUS ')]
rows=lambda name:[e for e in ev if e.get('ev')==name]
menu=rows('menu'); screens=rows('uiscreen'); states=rows('uistate'); laps=rows('laps'); confirm=rows('confirm'); start=rows('start')
checks={
 'Lisa/Family/default3': bool(menu) and menu[0].get('char')=='lisa' and menu[0].get('car')=='famil_v' and menu[0].get('laps')=='3',
 'track first': bool(screens) and screens[0].get('name')=='mmtrack',
 'Family native rating2': bool(states) and states[0].get('rate')=='2',
 'down clamp1': [int(e['laps']) for e in laps[:4]]==[2,1,1,1],
 'up clamp5': [int(e['laps']) for e in laps[4:]]==[2,3,4,5,5,5,5],
 'two Cross confirmations': [e.get('kind') for e in confirm]==['character','vehicle'],
 'START no advance': bool(start) and len(confirm)==2 and float(start[0]['t'])>float(confirm[1]['t']) and float(confirm[0]['t'])-float(menu[0]['t'])>7,
 'native END/errors0': not bad,
}
for k,v in checks.items(): print(('PASS ' if v else 'FAIL ')+k)
print('native:',d, 'start:',start, 'confirm:',confirm)
if red:
 caught=not checks['track first'] and not checks['down clamp1'] and not checks['two Cross confirmations']
 print('RED CAUGHT' if caught else 'RED NOT CAUGHT'); sys.exit(0 if caught and not bad else 1)
sys.exit(0 if all(checks.values()) else 1)
