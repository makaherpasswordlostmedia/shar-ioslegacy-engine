#!/usr/bin/env python3
"""Гейт REGPRE-гистерезис: по smoke.txt (строки «REGPRE aaaa->bbbb res=… at x,z t=…») — для каждого региона (бит) число ВКЛЮЧЕНИЙ в любом окне 10 с.
  regpre_hyst.py ПАПКА_ПРОГОНА [--max-rises 1]   -> строка REGPRE: PASS|FAIL … (код 0 / 1)"""
import re, sys
from pathlib import Path
d = Path(sys.argv[1]); lim = 1
if '--max-rises' in sys.argv: lim = int(sys.argv[sys.argv.index('--max-rises') + 1])
rises = {}   # бит -> [t, ...]
for l in (d / 'smoke.txt').read_text(errors='replace').splitlines():
    m = re.match(r'REGPRE ([0-9a-f]{4})->([0-9a-f]{4}) .* t=([0-9.]+)', l)
    if not m: continue
    a, b, t = int(m[1], 16), int(m[2], 16), float(m[3])
    for k in range(16):
        if (b >> k) & 1 and not (a >> k) & 1: rises.setdefault(k + 1, []).append(t)
worst, wk = 0, 0
for k, ts in rises.items():
    for t0 in ts:
        n = sum(1 for t in ts if t0 <= t < t0 + 10.0)
        if n > worst: worst, wk = n, k
tot = sum(len(v) for v in rises.values())
ok = worst <= lim
print(f"REGPRE: {'PASS' if ok else 'FAIL'} (включений всего {tot}, регионов {len(rises)}, максимум на регион за 10 с: {worst}{' в регионе %d' % wk if wk else ''}, порог {lim})")
sys.exit(0 if ok else 1)
