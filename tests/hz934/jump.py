#!/usr/bin/env python3
"""Разбор строк HZE (viewer/horizon.h, «flag hztrace 2») из smoke.txt: кромка нарисованной ленты, 72 азимута, угол места ×100.
По соседним положениям глаза (сдвиг 1…6 м, один уровень, один режим ленты) — скачок = p90 по азимутам |Δугла|, градусов; на режим берётся максимум по шагам.
  jump.py smoke.txt [--lim 5] [--red | --oldbuild]   без --red: PASS, если мировая лента (world=1) ≤ lim; с --red: PASS, если прежняя лента (world=0) > lim (гейт обязан краснеть на ней)"""
import sys, math, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('f'); ap.add_argument('--lim', type=float, default=5.); ap.add_argument('--red', action='store_true'); ap.add_argument('--oldbuild', action='store_true'); a = ap.parse_args()
rows = {0: [], 1: []}
for ln in open(a.f, errors='replace'):
    t = ln.split()
    if len(t) == 78 and t[0] == 'HZE': rows[int(t[5])].append((float(t[1]), float(t[3]), np.array(t[6:], float) / 100.))
res = {}
for w, rs in rows.items():
    rs = [r for k, r in enumerate(rs) if k + 1 == len(rs) or math.hypot(rs[k + 1][0] - r[0], rs[k + 1][1] - r[1]) > 0.5]   # на каждое положение глаза — последний кадр (лента устоялась; прежняя лента меняет клетку с запозданием, на стоящем глазе)
    mx = 0.; n = 0; seq = []
    for (x0, z0, e0), (x1, z1, e1) in zip(rs, rs[1:]):
        d = math.hypot(x1 - x0, z1 - z0)
        if not 1.0 <= d <= 6.0: continue
        j = float(np.percentile(np.abs(e1 - e0), 90)); n += 1; mx = max(mx, j); seq.append(j)
    res[w] = (mx, n, len(rs))
    print('лента %s: кадров %d, пар шагов %d, максимум p90 скачка %.1f°, медиана %.1f°' % ('мировая' if w else 'прежняя', len(rs), n, mx, float(np.median(seq)) if seq else -1))
if a.oldbuild:   # EBOOT с HZ_WORLD934_OLD=1: мировой ленты нет вовсе (строк world=1 нет), прежняя на месте и скачет
    ok = res.get(1, (0, 0, 0))[2] == 0 and res[0][1] >= 8 and res[0][0] > a.lim
    print('HZ934-ДВИЖОК-OLD: %s' % ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
w = 0 if a.red else 1
ok = res[w][1] >= 8 and ((res[w][0] > a.lim) if a.red else (res[w][0] <= a.lim))
print('HZ934-ДВИЖОК%s: %s' % ('-КРАСНЫЙ' if a.red else '', 'PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
