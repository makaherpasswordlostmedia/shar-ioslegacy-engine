#!/usr/bin/env python3
# №930г: x_city стоя (окна C_L4w / C_L7w, первые 2 секунды окна — устаивание). python3 tab.py out_X/smoke.txt ...
import re, sys, collections, statistics as st
for fn in sys.argv[1:]:
    W = collections.defaultdict(list); seen = collections.Counter()
    for l in open(fn, errors='ignore'):
        if not l.startswith('PHSEC'): continue
        m = re.search(r'scene=(C_L\dw)', l)
        if not m: continue
        seen[m.group(1)] += 1
        if seen[m.group(1)] < 3: continue
        W[m.group(1)].append(float(re.search(r'x_city=([\d.]+)', l).group(1)))
    print('%-34s' % fn.split('/')[-2], '  '.join('%s %.3f ±%.3f (n=%d)' % (k, st.mean(v), st.pstdev(v), len(v)) for k, v in sorted(W.items())))
