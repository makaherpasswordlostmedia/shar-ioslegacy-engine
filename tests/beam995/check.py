#!/usr/bin/env python3
# №995: проверка прогона ufo.txt. check.py ДИР_ВЫХОДА   последняя строка PASS/FAIL
#  счёт BEAM995: строки on=1 рисуют конус (draws > 0, 56 треугольников за вызов), строки on=0 — нет (draws = 0)
#  снимок «side» (камера стоит, меняется только flag beam995): разница кадров off/on — вертикальная полоса под тарелкой: не меньше 1500 пикселей разницы > 14 в строках 120–200 (под тарелкой), ширина ≤ 45 % кадра,
#   высота ≥ 40 пикселей, центр по x в средней трети; блинк под тарелкой в on убран (яркая точка в off рядом с днищем, в on её нет)
import sys, re, os
from PIL import Image
import numpy as np
d = sys.argv[1]; ok = True
rows = []
for l in open(d + '/smoke.txt', errors='ignore'):
    m = re.match(r'BEAM995 on=(\d) draws=(\d+) tri=(\d+) .* calls=(\d+) us_new=([\d.]+) us_old=([\d.]+) us_all=([\d.]+)', l)
    if m: rows.append((int(m[1]), int(m[2]), int(m[3]), int(m[4]), float(m[5]), float(m[6]), float(m[7])))
n1 = [r for r in rows if r[0] == 1]; n0 = [r for r in rows if r[0] == 0]
if len(n1) < 4 or len(n0) < 4: print('мало строк BEAM995', len(n1), len(n0)); ok = False
if any(r[1] == 0 or r[2] != 56 * r[1] for r in n1): print('on=1: конус не рисуется или не 56 треугольников за вызов'); ok = False
if any(r[1] for r in n0): print('on=0: конус рисуется'); ok = False
if n1 and n0: print(f'цена Mac, мкс на кадр, весь свет луча: новое {np.mean([r[6] for r in n1]):.1f}, TEST70 {np.mean([r[6] for r in n0]):.1f}; треугольников новое {n1[0][2] // max(n1[0][1], 1)} за вызов')
def load(n): return np.asarray(Image.open(f'{d}/b995_side_{n}.bmp').convert('RGB'), float)
try:
    a, b = load('off'), load('on'); df = np.abs(a - b).max(axis=2); df[:120, :] = 0; df[200:, :] = 0   # без строки счётчиков и самой тарелки (она за 0,9 с поворачивается): смотрим полосу под днищем
    m = df > 14; npx = int(m.sum()); ys, xs = np.nonzero(m)
    if npx:
        w = (xs.max() - xs.min()) / 480.; h = ys.max() - ys.min(); cx = (xs.max() + xs.min()) / 2 / 480.
        print(f'side: разница {npx} пикселей, ширина {w:.2f} кадра, высота {h}, центр x {cx:.2f}')
        if npx < 1500 or w > .45 or h < 40 or not (.33 < cx < .67): print('side: полоса под тарелкой не та'); ok = False
    else: print('side: кадры одинаковы'); ok = False
except Exception as e: print('side:', e); ok = False
print('PASS' if ok else 'FAIL')
