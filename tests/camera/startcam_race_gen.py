#!/usr/bin/env python3
"""Камеры старта гонок и бонусных миссий уровня N в режиме игрока. msnsel принимает бонус/гонку (msn_start_bonus) только из свободного хода: уровень пройден или история в первом этапе вступления
(viewer/mission/msn_run.c:555), поэтому перед КАЖДЫМ msnsel сценарий делает flag msn (сброс на старт уровня), а не идёт подряд после сюжетной миссии (так был «select-refused» на L3 sr1..bm1).
  .venv/bin/python tests/camera/startcam_race_gen.py N первый_индекс последний_индекс  -> stdout"""
import sys
n, a, b = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
out = [f'# Камеры старта гонок/бонусов L{n}, индексы {a}..{b}, режим игрока', f'scene L{n}_load', f'flag golevel {n}', 'wait 20', 'flag player 1']
for i in range(a, b + 1):
    out += [f'scene L{n}_race{i}', 'flag msn', 'wait 4', f'flag msnsel {i}', 'wait 1.5', f'shot l{n}_race{i}', 'wait 5', 'press cross 0.3', 'wait 1']
out.append('end'); print('\n'.join(out))
