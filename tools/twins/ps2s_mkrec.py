#!/usr/bin/env python3
"""Рецепт ходьбы Гомера из снимка гаража: python3 -I tools/twins/ps2s_mkrec.py ID 'кадр:кнопка:знач,...' КАДРОВ [шаг_png]
пример: ... walk1 '5:square:1,12:square:0,40:lup:0.53,40:lleft:0.85,190:lup:0,190:lleft:0' 300 10"""
import json, sys
rid, spec, n = sys.argv[1], sys.argv[2], int(sys.argv[3]); step = int(sys.argv[4]) if len(sys.argv) > 4 else 10
pad = [[int(a), b, float(c)] for a, b, c in (x.split(':') for x in spec.split(','))]
r = {'id': rid, 'state': 'build/twins/o4_s2/ps2s2_garage_boot/snap_6250.p2s', 'frames': n, 'every': 5,
     'trace': ['homer_root', 'cam_pos'], 'pad': pad, 'shots': [], 'pngs': [[30, n, step]], 'timeout': 600, 'renderer': 'metal'}
json.dump(r, open(f'build/ps2stend/rec/{rid}.json', 'w'), indent=1)
