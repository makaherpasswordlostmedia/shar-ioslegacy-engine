#!/usr/bin/env python3
"""Сценарий камер старта всех миссий уровня N (2..7) в режиме игрока (flag player 1, без flag startcam):
  .venv/bin/python tests/camera/startcam_levels_gen.py N [число_миссий]  ->  stdout (сценарий для tools/smoke.sh)
По msnsel i (MISSION SELECT, i — номер в таблице миссий уровня: основные, гонки, бонусные) на каждый старт: кадр через 1,5 с и ожидание конца камеры."""
import sys
n = int(sys.argv[1]); k = int(sys.argv[2]) if len(sys.argv) > 2 else 16
out = [f'# Камеры старта миссий L{n} в режиме игрока (tests/camera/startcam_levels_gen.py): msnsel 0..{k-1}', f'scene L{n}_load', f'flag golevel {n}', 'wait 20', 'flag player 1', 'flag msn', 'wait 8']   # flag player в первой строке включает путь «игрок с логотипов» (PLAYERFIRST): ставить после загрузки уровня
for i in range(k):
    out += [f'scene L{n}_sel{i}', f'flag msnsel {i}', 'wait 1.5', f'shot l{n}_sel{i}', 'wait 5', 'press cross 0.3', 'wait 1']   # крест в конце: пропуск ролика/этапа, чтобы финальная миссия с FMV не держала остальные сцены
out.append('end'); print('\n'.join(out))
