#!/usr/bin/env python3
# №791: сценарии трамплинов (a331_jumps_v3 из библиотеки) для трёх видов камеры SELECT: дальний, бампер, ближний; + замеры camingeom/diaglog
import sys, os
src = '/Users/USER/Downloads/shar-psp/knowledge/twins_library/сценарии/a331_jumps_v3__9c9a5f3da5.txt'
out = os.path.dirname(os.path.abspath(__file__))   # сценарии ложатся рядом (tests/camera/cam791)
body = open(src, encoding='utf-8').read()
for v, n in (('far', 0), ('bumper', 1), ('near', 2)):
    head = ['flag player 1', 'flag camingeom 1', 'flag diaglog 1']
    for _ in range(n): head += ['press select 0.2', 'wait 1']
    i = body.index('wait 3\n') + len('wait 3\n')   # «flag player 1» до игры уводит старт в заставку и меню (PLAYERFIRST 1): после первого wait
    open(os.path.join(out, 'jumps_%s.txt' % v), 'w', encoding='utf-8').write(body[:i] + '\n'.join(head) + '\n' + body[i:])
# пешком у стен, узких проходов, машин и прохожих, камера обходит Гомера по кругу (a331_foot_v3): тот же замер
src = '/Users/USER/Downloads/shar-psp/knowledge/twins_library/сценарии/a331_foot_v3__ef6f00db02.txt'
body = open(src, encoding='utf-8').read(); i = body.index('wait 3\n') + len('wait 3\n')
open(os.path.join(out, 'foot_walls.txt'), 'w', encoding='utf-8').write(body[:i] + 'flag player 1\nflag camingeom 1\nflag diaglog 1\n' + body[i:])
print('ok')
