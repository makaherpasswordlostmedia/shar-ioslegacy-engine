#!/usr/bin/env python3
"""Эмуляторная часть гейта №952: tests/tex952/emu952.py ПАПКА_СТАРЫЕ ПАПКА_НОВЫЕ — прогоны tests/toon/flat912_scenario.txt со старым flat912.bin (выпуск) и с новым (№952).
Снимки h<i>_new (заливка включена): 1) оба прогона дошли до END и движок прочёл список (FLATLIST ok=1); 2) движок считает заливок (строка FLAT on=1 flat=N) на ≥ 10 больше, чем со старым списком (стены перешли в заливку; пикселями это не видно: тон заливки почти равен среднему цвету рельефа, поэтому разницу кадров только печатаем);
3) средний цвет кадра не разошёлся больше чем на 6 из 255; 4) дыр (пурпур) не больше, чем было, +5. Код 0 — PASS."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
a, b = Path(sys.argv[1]), Path(sys.argv[2]); bad = []; best = 0.
for r in (a, b):
    t = (r / 'smoke.txt').read_text(errors='replace')
    if 'END' not in t.split(): bad.append(f'{r.name}: сценарий не дошёл до END')
    if not re.search(r'FLATLIST level=1 ok=1', t): bad.append(f'{r.name}: движок не прочёл flat912.bin')
px = lambda r, n: np.asarray(Image.open(r / f'{n}.png').convert('RGB')).astype(int)
hole = lambda x: int(((x[..., 0] > 200) & (x[..., 1] < 60) & (x[..., 2] > 200)).sum())
for i in range(6):
    try: o, w = px(a, f'h{i}_new'), px(b, f'h{i}_new')
    except FileNotFoundError: continue
    d = (np.abs(o - w).sum(axis=2) > 24).mean() * 100; dm = np.abs(o.mean(axis=(0, 1)) - w.mean(axis=(0, 1))).max(); ho, hw = hole(o), hole(w); best = max(best, d)
    print(f'вид {i}: отличий {d:.2f} %, разница среднего цвета {dm:.1f}, дыр было {ho} стало {hw}')
    if dm > 6: bad.append(f'вид {i}: средний цвет разошёлся на {dm:.1f}')
    if hw > ho + 5: bad.append(f'вид {i}: дыр стало больше ({ho} → {hw})')
def flatN(r):
    m = re.findall(r'^FLAT on=1 flat=(\d+)', (r / 'smoke.txt').read_text(errors='replace'), re.M); return max(map(int, m)) if m else -1
fo, fn = flatN(a), flatN(b); print(f'заливок в движке: было {fo}, стало {fn}')
if fn - fo < 10: bad.append(f'заливок прибавилось {fn - fo} (< 10): правило не дошло до движка')
for x in bad: print('FAIL', x)
print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
