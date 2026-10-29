#!/usr/bin/env python3
"""Compare host_check (viewer/skin.c compiled for the Mac) with the Python mirror in tools/char_export.py."""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))
import char_export as ce

m = ce.read_chr(ROOT / 'build/chars/homer.chr'); names = [c['name'] for c in m['clips']]
worst = 0.; n = 0; roots = 0
for line in open(sys.argv[1]):
    p = line.split()
    if p[0] == 'P':
        c = names.index(p[1]); t = float(p[2]); j = int(p[3]); got = np.array(p[4:], float).reshape(4, 3).T
        pal, _ = ce.palette(m, ce.sample_local(m, c, t)); worst = max(worst, np.abs(pal[j] - got).max()); n += 1
    elif p[0] == 'B':
        a, ta, b, tb, w, j = names.index(p[1]), float(p[2]), names.index(p[3]), float(p[4]), float(p[5]), int(p[6])
        la, lb = ce.sample_local(m, a, ta), ce.sample_local(m, b, tb)
        mix = [(ce.qmix(qa, qb, w), pa + (pb - pa) * w) for (qa, pa), (qb, pb) in zip(la, lb)]
        pal, _ = ce.palette(m, mix); got = np.array(p[7:], float).reshape(4, 3).T
        worst = max(worst, np.abs(pal[j] - got).max()); n += 1
    elif p[0] == 'R':
        c = names.index(p[1]); t = float(p[2]); tr = m['clips'][c]['tracks'][0]
        exp = np.zeros(3) if tr['tf'] is None else None
        if exp is None:
            a, b, u = ce._key(tr['tf'], tr['tv'], min(max(t * m['clips'][c]['fps'], 0), m['clips'][c]['frames'] - 1)); exp = a + (b - a) * u
        worst = max(worst, np.abs(exp - np.array(p[3:6], float)).max()); roots += 1
    else: print(line.strip())
print(f'{n} palette matrices + {roots} root offsets compared, max abs difference C vs Python = {worst:.2e}')
sys.exit(0 if worst < 1e-3 else 1)
