#!/usr/bin/env python3
"""Проверки гейта №912 по папке прогона (smoke.txt и снимки h<i>_new/old.png); код выхода 0 — PASS."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
run = Path(sys.argv[1]); text = (run / 'smoke.txt').read_text(errors='replace'); bad = []
if 'END' not in text.split(): bad.append('сценарий не дошёл до END')
if not re.search(r'FLATLIST level=1 ok=1', text): bad.append('движок не прочёл flat912.bin (FLATLIST ok=1)')
scn = (run / 'scenario.txt').read_text(errors='replace') if (run / 'scenario.txt').exists() else ''
if re.search(r'^flag marks918old 1', scn, re.M) and not re.search(r'MARKSLIST level=1 ok=1', text): bad.append('движок не прочёл marks912.bin (MARKSLIST ok=1)')   # №918: слой разметки выключен по умолчанию — файл читается только с flag marks918old 1 (FLAT912_MARKS=1 в flat912.sh)
def px(n):
    a = np.asarray(Image.open(run / f'{n}.png').convert('RGB')).astype(int); return a
n = 0; rows = []
for i in range(6):
    try: o, w = px(f'h{i}_old'), px(f'h{i}_new')
    except FileNotFoundError: bad.append(f'нет снимков вида {i}'); continue
    diff = (np.abs(o - w).sum(axis=2) > 24).mean(); dm = np.abs(o.mean(axis=(0, 1)) - w.mean(axis=(0, 1))).max()
    hole = lambda a: int(((a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)).sum())
    ho, hw = hole(o), hole(w); rows.append((i, round(diff * 100, 1), round(dm, 1), ho, hw))
    if diff < 0.01: bad.append(f'вид {i}: заливка не меняет картинку (красный контроль)')
    if dm > 10: bad.append(f'вид {i}: средний цвет разошёлся на {dm:.1f}')
    if hw > ho + 5: bad.append(f'вид {i}: дыр с заливкой {hw}, с текстурами {ho}')
for r in rows: print('вид %d: отличий %.1f %%, разница среднего цвета %.1f, дыр текстуры %d / заливка %d' % r)
for b in bad: print('FAIL', b)
print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
