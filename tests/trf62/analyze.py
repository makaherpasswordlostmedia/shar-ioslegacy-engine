#!/usr/bin/env python3
# №930в (t62/trf): цена трафика на Маке по сценам и состояниям заливки. python3 analyze.py out_X/smoke.txt [...]  -> на сцену и on=0/1: x_trf, trf_cars, число машин, мс на машину (Mac и ×5,8 PSP)
import re, sys, statistics as st
K = 5.8
def run(fn):
    rows = {}
    on = None; last_on_t = 0.0; prev = None; skip = 0
    for l in open(fn, errors='ignore'):
        m = re.match(r'CARFILL t=([\d.]+) .*? on=(\d)', l)
        if m:
            t = float(m.group(1)); o = int(m.group(2))
            if o != on: on = o; skip = 2   # две секунды после переключения (перекраска) не считаем
            continue
        m = re.match(r'PHSUB t=([\d.]+) scene=(\S+)', l)
        if m and on is not None:
            if skip > 0: skip -= 1; continue
            sc = m.group(2)
            d = {k: float(v) for k, v in re.findall(r'(trf_cars|trf_peds)=([\d.]+)', l)}
            n = re.search(r'trf_n=([\d.]+)/([\d.]+)/([\d.]+)', l)
            d['cars'] = float(n.group(1)) + float(n.group(2)) if n else 0
            rows.setdefault((sc, on), []).append(d)
    return rows
for fn in sys.argv[1:]:
    print('==', fn)
    R = run(fn)
    for (sc, on), L in sorted(R.items()):
        tc = sum(x.get('trf_cars', 0) for x in L); nc = sum(x['cars'] for x in L)
        print('%-8s on=%d n=%2d  trf_cars=%.3f мс  машин=%.2f  на машину=%.3f мс Mac = %.2f мс PSP' % (sc, on, len(L), tc / len(L), nc / len(L), (tc / nc) if nc else 0, (tc / nc) * K if nc else 0))
