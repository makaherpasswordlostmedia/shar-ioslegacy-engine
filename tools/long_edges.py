#!/usr/bin/env python3
"""Гейт №674: в ближних версиях города (SHR7, owner 0) нет треугольников с ребром длиннее порога (по умолчанию 14,5 м: стены режутся до 14 м, пол до 7 м).
  python3 tools/long_edges.py level.shr [порог_м] [--expect-fail]
Источник таких треугольников до SHR_SPLIT_LONG=1: веер юбки шва (skirts.skirt_soup), 216–273 на уровень, до 55 м. Код возврата 1, если есть."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, shr7read as R
a = [x for x in sys.argv[1:] if not x.startswith('--')]
th = float(a[1]) if len(a) > 1 else 14.5
P = R.load(a[0], far=False)['P']
e = np.max(np.stack([np.linalg.norm(P[:, i] - P[:, (i + 1) % 3], axis=1) for i in range(3)]), axis=0)
n = int((e > th).sum()); ok = n == 0
if '--expect-fail' in sys.argv: print(f'{a[0]}: ребро > {th} м: {n}, макс {e.max():.1f} м; красный контроль {"PASS (поймал)" if not ok else "FAIL (не поймал)"}'); sys.exit(0 if not ok else 1)
print(f'{a[0]}: треугольников {len(P)}, ребро > {th} м: {n}, макс {e.max():.1f} м: {"PASS" if ok else "FAIL"}'); sys.exit(0 if ok else 1)
