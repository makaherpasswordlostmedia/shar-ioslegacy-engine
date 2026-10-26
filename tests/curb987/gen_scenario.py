#!/usr/bin/env python3
"""№987: сценарий «было / стало» по уровням 1–7: обычный старт уровня (flag golevel), камера над уголками и длинным бордюром. gen_scenario.py > scenario.txt"""
import math
SP = {  # уровень: [(имя, x, y, z, смещение камеры dx, dy, dz)]
 1: [('C1', -193, 3.7, 93), ('C2', -293, 3.7, 94), ('K', -138, 3.7, 269)],
 2: [('C1', 211, 5.5, 53), ('C2', -178, 7.3, -17), ('K', -213, 18.0, -53)],
 3: [('K1', 55, -2.8, 109), ('K2', 91, -1.9, 97)],
 4: [('C1', -193, 3.7, 93), ('K', -138, 3.7, 269)],
 5: [('C1', 211, 5.5, 53), ('K', -213, 18.0, -53)],
 6: [('K1', 54, -2.8, 110)],
 7: [('C1', 218, -2.0, 484), ('C2', 335, 2.6, -113), ('K', 24, 4.6, 546)],
}
OFF = (6.0, 4.5, 6.0)
print('scene C_BOOT\nflag cfgdefaults 1\nwait 6')
for L, spots in SP.items():
    print(f'scene C_L{L}\nflag golevel {L}\nwait 40')
    for nm, x, y, z in spots:
        dx, dy, dz = OFF; n = math.sqrt(dx * dx + dy * dy + dz * dz)
        print(f'scene S_L{L}_{nm}\nfoot {x} {z} 0\nwait 4\ncam {x + dx:.1f} {y + dy:.1f} {z + dz:.1f} {-dx / n:.3f} {-dy / n:.3f} {-dz / n:.3f}\nwait 8\nshot L{L}_{nm}')
print('end')
