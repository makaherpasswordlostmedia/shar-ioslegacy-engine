#!/usr/bin/env python3
# Б TEST57: сценарий «стоять у каждых ворот регионов при свободной куче у границы» для одного уровня.
# gen.py gates.json УРОВЕНЬ СВОБОДНО_МБ [СЕК_ЗАМЕРА [ЧИСЛО_ВОРОТ]] > сценарий; метка сцены P<уровень>_<ворота>
import json, sys
g = [x for x in json.load(open(sys.argv[1])) if x['lv'] == int(sys.argv[2])]; hl = sys.argv[3]; meas = int(sys.argv[4]) if len(sys.argv) > 4 else 6
# Гомер пешком: на L1 и L2 игрок после загрузки на ногах, а goto двигает только машину; поток клеток и ворота REGPRE смотрят на глаз камеры, ему всё равно (пешком или в машине)
o = ['wait 12', 'scene LOAD', f'flag golevel {sys.argv[2]}', 'wait 40', 'flag cfgdefaults 1', 'scene FOOT', 'wait 6', 'flag stop']
if len(sys.argv) > 5: g = g[:int(sys.argv[5])]
for x in g:
    o += [f'scene P{x["lv"]}_{x["i"]}', f'foot {x["c"][0]} {x["c"][2]} 4.712', 'wait 4', f'flag heapleft {hl}', f'wait {meas}', 'flag heapleft 99', 'wait 1']
o += ['end']
print('\n'.join(o))
