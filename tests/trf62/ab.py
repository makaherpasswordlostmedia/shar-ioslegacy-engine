#!/usr/bin/env python3
# №930в: средняя цена трафика (PHSUB trf_cars, мс Mac на кадр) в окнах фиксированной сцены, на машину. python3 ab.py СЦЕНА out_X/smoke.txt ... ; сцена — T_L3S / T_L5 / T_L7
import re, sys
def stat(fn, scene):
    first = {}; L = []
    for l in open(fn, errors='ignore'):
        m = re.match(r'PHSUB t=([\d.]+) scene=(\S+)', l)
        if not m: continue
        t = float(m.group(1)); sc = m.group(2); first.setdefault(sc, t)
        if sc != scene or t - first[sc] < 46: continue
        c = float(re.search(r'trf_cars=([\d.]+)', l).group(1)); n = re.search(r'trf_n=([\d.]+)/([\d.]+)', l)
        L.append((c, float(n.group(1)) + float(n.group(2))))
    return L
if __name__ == '__main__':
    for fn in sys.argv[2:]:
        L = stat(fn, sys.argv[1]); c = sum(x[0] for x in L) / max(len(L), 1); n = sum(x[1] for x in L) / max(len(L), 1)
        print('%-40s n=%d trf_cars=%.3f мс Mac (%.2f PSP)  машин=%.2f  на машину=%.4f' % (fn.split('/')[-2], len(L), c, c * 5.8, n, c / n if n else 0))
