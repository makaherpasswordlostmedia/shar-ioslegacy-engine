#!/usr/bin/env python3
"""№907: сравнение кадров орбиты вокруг автомата. python compare.py OUT_OLD OUT_TRUTH OUT_NEW   (каталоги с o_00.png .. o_11.png)
 OLD   — прежний код на данных диска (дефект);  TRUTH — прежний код на данных с снятым флагом 2 в файле (эталон не из кода правила);
 NEW   — код с правилом на данных диска. Условия: NEW == TRUTH (<= TOL px на каждом азимуте), OLD != TRUTH (>= MIN px минимум на двух азимутах)."""
import sys
import numpy as np
from PIL import Image
TOL, MIN, DIFF = 3000, 10000, 40   # TOL: контур мультика на кромке предмета гуляет на пиксель (до ~2200 px на азимут); дефект — 17–40 тыс. px
def d(a, b):
    x = np.asarray(Image.open(a).convert('RGB'), int); y = np.asarray(Image.open(b).convert('RGB'), int)
    return int((np.abs(x - y).sum(2) > DIFF).sum())
old, truth, new = sys.argv[1:4]
rows = []
for k in range(12):
    f = 'o_%02d.png' % k
    rows.append((k, d(old + '/' + f, truth + '/' + f), d(new + '/' + f, truth + '/' + f)))
for k, a, c in rows: print('азимут %02d: прежний-эталон %6d px, новый-эталон %6d px' % (k, a, c))
bad_new = [k for k, a, c in rows if c > TOL]; shown = [k for k, a, c in rows if a >= MIN]
ok1, ok2 = not bad_new, len(shown) >= 2
print('%s новый == эталон на всех азимутах (<= %d px); нарушены: %s' % ('OK' if ok1 else 'КРАСНОЕ', TOL, bad_new))
print('%s прежний отличается от эталона на %d азимутах (нужно >= 2, порог %d px)' % ('OK' if ok2 else 'КРАСНОЕ', len(shown), MIN))
sys.exit(0 if ok1 and ok2 else 1)
