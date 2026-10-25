#!/usr/bin/env python3
# №930г: check.py gate A B ДОПУСК — x_city стоя на L4 и L7 у A не выше, чем у B + допуск (мс Мак); код возврата 0 — прошло
import re, sys, collections, statistics as st
def city(fn):
    W = collections.defaultdict(list); seen = collections.Counter()
    for l in open(fn, errors='ignore'):
        if not l.startswith('PHSEC'): continue
        m = re.search(r'scene=(C_L\dw)', l)
        if not m: continue
        seen[m.group(1)] += 1
        if seen[m.group(1)] < 3: continue
        W[m.group(1)].append(float(re.search(r'x_city=([\d.]+)', l).group(1)))
    return {k: (st.mean(v), len(v)) for k, v in W.items()}
a = city(sys.argv[2]); b = city(sys.argv[3]); tol = float(sys.argv[4]); ok = bool(a) and set(a) == set(b)
for k in sorted(a):
    if k in b:
        d = a[k][0] - b[k][0]; print('  %s: %.3f против %.3f (Δ %+.3f мс Мак = %+.2f PSP), допуск %.3f, окон %d/%d' % (k, a[k][0], b[k][0], d, d * 5.8, tol, a[k][1], b[k][1]))
        ok = ok and d <= tol and a[k][1] >= 6 and b[k][1] >= 6
sys.exit(0 if ok else 1)
