#!/usr/bin/env python3
"""Рецепт стенда 2: из снимка старта в машине: убрать обучение, постоять (вид сзади), выйти (треугольник), вернуться.
python3 -I tools/twins/ps2s_seat_recipe.py ID СНИМОК.p2s → build/ps2stend/rec/ID.json
Кадры: 50 к/с, значит каждые 5 кадров = 0,1 с."""
import json, sys
rid, snap = sys.argv[1], sys.argv[2]
r = {'id': rid, 'state': snap, 'frames': 620, 'every': 20, 'trace': ['mat[12]', 'mat[13]', 'mat[14]'],
     'pad': [[5, 'square', 1], [12, 'square', 0], [200, 'triangle', 1], [206, 'triangle', 0],
             [420, 'triangle', 1], [426, 'triangle', 0]],
     'shots': [], 'pngs': [[60, 180, 40], [195, 330, 5], [415, 560, 5]], 'timeout': 900, 'renderer': 'metal'}
json.dump(r, open(f'build/ps2stend/rec/{rid}.json', 'w'), indent=1)
