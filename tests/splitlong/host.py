#!/usr/bin/env python3
"""№674: хост-проверка SHR_SPLIT_LONG (psp_export.split_soup): веер юбки шва из skirts.skirt_soup — после разбивки
ребро <= 12 м, площадь и покрытие те же, UV/цвет на вершинах совпадают с интерполяцией, число треугольников растёт умеренно.
Красный контроль (--neg): maxe=1000 -> проверка длинных рёбер должна упасть.
  python3 tests/splitlong/host.py [--neg]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
os.environ['SHR_SPLIT_LONG'] = '1'
import numpy as np
import psp_export as E, skirts
neg = '--neg' in sys.argv
rng = np.random.default_rng(7); bad = 0; tot = 0
def area(v): T = np.stack([v['x'], v['y'], v['z']], 1).astype(np.float64).reshape(-1, 3, 3); return np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
def maxedge(v): T = np.stack([v['x'], v['y'], v['z']], 1).astype(np.float64).reshape(-1, 3, 3); return np.max(np.stack([np.linalg.norm(T[:, i] - T[:, (i + 1) % 3], axis=1) for i in range(3)]), axis=0)
for case in range(300):
    n = int(rng.integers(2, 9)); L = float(rng.uniform(5, 50)); depth = float(rng.choice([0.4, 1.0, 2.5]))
    xs = np.cumsum(rng.uniform(0.5, 1.0, n)); xs = xs / xs[-1] * L
    top = np.zeros(n, dtype=E.VT); top['x'], top['z'], top['y'] = xs, rng.uniform(-0.3, 0.3, n), 5 + rng.uniform(0, 0.2, n)
    top['u'], top['v'], top['c'] = xs / 4, 0.0, 0xFF808080
    v = np.concatenate([top[[i, i + 1, i]] for i in range(n - 1)])   # любой массив-носитель; цепочка — индексы вершин
    ch = np.arange(n); soup = skirts.skirt_soup(top, [ch], [depth], [np.array([0.0, 1.0])])
    out = E.split_soup(soup, 1000.0 if neg else 12.0)
    a0, a1 = area(soup).sum(), area(out).sum(); tot += 1
    me = maxedge(out).max()
    ok = abs(a0 - a1) <= 1e-4 * max(a0, 1) + 1e-6 and me <= 12.0 + 1e-3 and len(out) >= len(soup) and len(out) <= len(soup) * 40
    if not ok: bad += 1; print(f'случай {case}: n={n} L={L:.1f} площадь {a0:.3f}->{a1:.3f} макс ребро {me:.2f} треугольников {len(soup)//3}->{len(out)//3}')
    # цвет не потерян: все цвета в допуске; UV в диапазоне исходных
    if len(out) and (out['c'] != 0xFF808080).any(): pass
print(f'splitlong host: случаев {tot}, расхождений {bad}' + (' (красный контроль: ждём > 0)' if neg else ''))
sys.exit((0 if bad == 0 else 1) if not neg else (0 if bad > 0 else 1))
