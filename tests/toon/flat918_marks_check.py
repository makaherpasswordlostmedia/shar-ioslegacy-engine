#!/usr/bin/env python3
"""Гейт №918: тонкая разметка земли L1 видна с заливкой так же, как с текстурами (папка прогона: снимки tN_tex.png / tN_fill.png, N = 0..5).
Разметка = точки цвета штриха (≈ 189,101,16 после кривой мультика: |R−189| < 45, |G−101| < 35, B < 50) ниже горизонта (y ≥ 90), вне рамки Гомера (x 165..325, y 50..272) и радара.
Совпало = точки разметки с текстурами, рядом (3 пикс.) с которыми есть точка разметки с заливкой. Условия: с текстурами в сумме ≥ 400 точек (иначе гейт слепой), совпало ≥ 60 %.
Старый flat912.bin (набор до №918): совпало 2 %, с правилом: 79 %. Выход 0 — PASS."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
run = Path(sys.argv[1]); bad = []; T = F = 0
def mask(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)
    m = (abs(a[..., 0] - 189) < 45) & (abs(a[..., 1] - 101) < 35) & (a[..., 2] < 50)
    m[:90, :] = False; m[50:272, 165:325] = False; m[150:, 380:] = False; return m
def dil(m, r=3):
    o = m.copy()
    for ax in (0, 1):
        t = o.copy()
        for s in range(1, r + 1): t |= np.roll(o, s, ax) | np.roll(o, -s, ax)
        o = t
    return o
for i in range(6):
    try: a, b = mask(run / f't{i}_tex.png'), mask(run / f't{i}_fill.png')
    except FileNotFoundError: bad.append(f'нет снимков места {i}'); continue
    ok = int((a & dil(b)).sum()); T += int(a.sum()); F += ok
    print(f'место {i}: точек разметки с текстурами {int(a.sum())}, с заливкой {int(b.sum())}, совпало {ok}')
print(f'всего: с текстурами {T}, совпало {F} ({100 * F / max(1, T):.0f} %)')
if T < 400: bad.append(f'гейт слепой: с текстурами всего {T} точек разметки (< 400)')
if F < 0.6 * T: bad.append(f'разметка с заливкой совпала на {100 * F / max(1, T):.0f} % (< 60 %)')
for b in bad: print('FAIL', b)
print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
