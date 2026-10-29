#!/usr/bin/env python3
"""Лист было/стало правки 411 по прогону tests/fartint/run.sh: на уровень — вид с наибольшей маской дальнего города.
Столбцы: F (прежняя дымка) | A (без дымки) | Q (прежняя заглушка: цвет вершин) | P (заглушка тоном горизонта). sheet.py DIR OUT.png"""
import sys, glob, numpy as np
from PIL import Image, ImageDraw
d, out = sys.argv[1], sys.argv[2]
def cnt(p):
    M = np.asarray(Image.open(p).convert('RGB')).astype(int); return int(((M[..., 0] > 200) & (M[..., 1] < 70) & (M[..., 2] > 200)).sum())
W = Image.new('RGB', (4 * 480, 7 * 272 + 24), (20, 20, 20)); dr = ImageDraw.Draw(W)
for i, t in enumerate(['OLD: fog', 'NEW: no fog', 'OLD placeholder: vertex colour', 'NEW placeholder: horizon tone']): dr.text((i * 480 + 8, 6), t, fill=(255, 255, 255))
for n in range(1, 8):
    ms = glob.glob(f'{d}/L{n}h*_M.png')
    if not ms: continue
    b = max(ms, key=cnt)[:-6]
    for i, k in enumerate('FAQP'): W.paste(Image.open(f'{b}_{k}.png').convert('RGB'), (i * 480, 24 + (n - 1) * 272))
    dr.text((8, 24 + (n - 1) * 272 + 252), b.split('/')[-1], fill=(255, 255, 0))
W.save(out); print(out)
