#!/usr/bin/env python3
# city984_emu.py smoke.txt [smoke_B.txt]: средние PHSEC по маршрутам CITY_L<lv>_r<k> (первая секунда окна — устаивание); с двумя файлами — разница В−А в мс Мака и ×5,8 (≈ PSP)
import re, sys, collections
KEYS = ['n', 'build', 'x_city', 'x_props', 'x_trf', 'x_car', 'x_car3d', 'x_homer', 'x_fx', 'ph1', 'ph5', 'ph7']
def load(fn):
    acc = collections.defaultdict(lambda: collections.defaultdict(list)); seen = collections.Counter()
    for l in open(fn, errors='ignore'):
        if not l.startswith('PHSEC'): continue
        m = re.search(r'scene=(CITY_L(\d)_r(\d))', l)
        if not m: continue
        seen[m.group(1)] += 1
        if seen[m.group(1)] < 2: continue
        d = dict(re.findall(r'(\w+)=([-\d.]+)', l))
        for k in KEYS:
            if k in d: acc[m.group(1)][k].append(float(d[k]))
    return acc
def mean(l): return sum(l) / len(l) if l else float('nan')
A = load(sys.argv[1]); B = load(sys.argv[2]) if len(sys.argv) > 2 else None
print('%-12s ' % 'маршрут' + ' '.join('%7s' % k for k in KEYS))
tot = collections.defaultdict(lambda: collections.defaultdict(list))
for sc in sorted(A):
    print('%-12s ' % sc + ' '.join('%7.2f' % mean(A[sc][k]) for k in KEYS))
    if B and sc in B:
        print('%-12s ' % '  после' + ' '.join('%7.2f' % mean(B[sc][k]) for k in KEYS))
        print('%-12s ' % '  Δ×5,8' + ' '.join('%+7.2f' % (5.8 * (mean(B[sc][k]) - mean(A[sc][k])) if k != 'n' else mean(B[sc][k]) - mean(A[sc][k])) for k in KEYS))
        for k in KEYS: tot[0][k].append(mean(B[sc][k]) - mean(A[sc][k]))
if B and tot: print('СРЕДНЕЕ Δ мс Мака по маршрутам, ×5,8 (≈ PSP): ' + ', '.join('%s %+.2f' % (k, 5.8 * mean(tot[0][k])) for k in KEYS if k != 'n'))
