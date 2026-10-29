#!/usr/bin/env python3
"""Гейт правки 428 «мультяшный режим» (расширение порта): контур есть, когда режим включён, и только тогда.
Кадры прогона tests/toon/scenario.txt: foot_t0 / foot_t0b — Гомер пешком, режим выкл (два кадра подряд: шум), foot_t1 — вкл.
Контур = почти чёрные пиксели (max(R,G,B) < 24). Проходит, если прирост чёрных t1−t0 больше шума |t0b−t0| (меряется, не задаётся).
Цена: строки сводки сцен *_t0 / *_t1 (work p95, пик списка GE) и TOON в smoke.txt — в отчёт. gate.py DIR"""
import sys, re, numpy as np
from PIL import Image
d = sys.argv[1]
def blk(n): a = np.asarray(Image.open(f'{d}/{n}.png').convert('RGB')).astype(int); a = a[:, :370]; return int((a.max(2) < 24).sum())
b0, b0b, b1 = blk('foot_t0'), blk('foot_t0b'), blk('foot_t1')
noise = abs(b0b - b0); gain = b1 - b0; ok = gain > noise
print(f'чёрных пикселей: выкл {b0}, выкл повтор {b0b} (шум {noise}), вкл {b1} (прирост {gain})  {"PASS" if ok else "FAIL"}')
for ln in open(f'{d}/summary.txt', errors='replace'):
    if re.match(r'(drive|foot|L2)_t[01]\s', ln): print(ln.rstrip())
sys.exit(0 if ok else 1)
