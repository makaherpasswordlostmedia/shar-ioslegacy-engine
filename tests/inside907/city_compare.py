#!/usr/bin/env python3
"""№907-город: кадры L1 (частокол у озера и др., city_l1.txt: 4 места × 2 вида, p<место>_<вид>.png). python city_compare.py OUT_OLD OUT_TRUTH OUT_NEW
OLD — прежний код на данных диска; TRUTH — прежний код на данных, где флаг 2 снят в файле (mkref_city.py); NEW — код с правилом на данных диска.
Условия: NEW == TRUTH на всех кадрах (<= TOL px вне шапки), OLD != TRUTH минимум на двух кадрах (>= MIN px)."""
import sys
import numpy as np
from PIL import Image
TOL, MIN, DIFF, HUD = 300, 1000, 40, 70
def d(a, b):
    x = np.asarray(Image.open(a).convert('RGB'), int)[HUD:]; y = np.asarray(Image.open(b).convert('RGB'), int)[HUD:]
    return int((np.abs(x - y).sum(2) > DIFF).sum())
old, truth, new = sys.argv[1:4]; rows = []
for n in range(4):
    for v in range(2):
        f = 'p%d_%d.png' % (n, v); rows.append((n, v, d(old + '/' + f, truth + '/' + f), d(new + '/' + f, truth + '/' + f)))
for n, v, a, c in rows: print('место %d вид %d: прежний-эталон %5d px, новый-эталон %5d px' % (n, v, a, c))
bad = [(n, v) for n, v, a, c in rows if c > TOL]; shown = [1 for n, v, a, c in rows if a >= MIN]
ok1, ok2 = not bad, len(shown) >= 2
print('%s новый == эталон на всех кадрах (<= %d px); нарушены: %s' % ('OK' if ok1 else 'КРАСНОЕ', TOL, bad))
print('%s прежний отличается от эталона на %d кадрах (нужно >= 2, порог %d px)' % ('OK' if ok2 else 'КРАСНОЕ', len(shown), MIN))
sys.exit(0 if ok1 and ok2 else 1)
