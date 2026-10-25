#!/usr/bin/env python3
"""№949 перепись шума земли: для каждого куска с шумом (заливка земли, tstat[4]&4) период шума в метрах по родным UV: метров на единицу UV по u и по v (тайл шума = 1.0 UV).
  census.py НАБОР [--json out.json]"""
import sys, struct, json
from pathlib import Path
import numpy as np
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent.parent / 'tools'))
import flat_list as F
import shr7read as S

def pieces(path):
    """-> список кусков: dict(pi, tex, fl, cell, area, Lu, Lv (медианы по площади), ntri)"""
    d = S.load(path)
    P, UV, TEX, FL, PI = d['P'], d['UV'], d['TEX'], d['FL'], d['PI']
    # UV читаются как u16/256; разность берём по модулю 256 (повтор), знак по короткой дуге
    def wrap(x): return (x + 128.0) % 256.0 - 128.0
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]
    d1 = wrap(UV[:, 1] - UV[:, 0]); d2 = wrap(UV[:, 2] - UV[:, 0])
    det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    area = np.linalg.norm(np.cross(e1, e2), axis=1) * .5
    ok = (np.abs(det) > 1e-9) & (area > 1e-6)
    inv = np.zeros((len(det), 2, 2)); dd = np.where(ok, det, 1.0)
    # G = D^-1 E ; D = [[du1, dv1],[du2, dv2]] (строки — рёбра)
    inv[:, 0, 0] = d2[:, 1] / dd; inv[:, 0, 1] = -d1[:, 1] / dd; inv[:, 1, 0] = -d2[:, 0] / dd; inv[:, 1, 1] = d1[:, 0] / dd
    gu = inv[:, 0, 0, None] * e1 + inv[:, 0, 1, None] * e2   # dP/du
    gv = inv[:, 1, 0, None] * e1 + inv[:, 1, 1, None] * e2
    Lu = np.linalg.norm(gu, axis=1); Lv = np.linalg.norm(gv, axis=1)
    return d, area, Lu, Lv, ok

def wmedian(x, w):
    o = np.argsort(x); c = np.cumsum(w[o]); return float(x[o][np.searchsorted(c, c[-1] * .5)])

def main():
    pk = Path(sys.argv[1]); res = {}
    files = [('L1', pk / 'level.shr')] + [(f'L{n}', pk / f'l{n}' / 'level.shr') for n in range(2, 8)]
    for name, lv in files:
        if not lv.exists(): continue
        data, rows, sig = F.build(str(lv)); d, area, Lu, Lv, ok = pieces(str(lv))
        noisetex = {i for i, (k, why) in enumerate(rows) if k == 1}   # проверка ground — ниже
        f, tex, _ = F.load_level(str(lv)); noisetex = {i for i in noisetex if tex[i]['ground']}
        out = []
        PIs = np.unique(d['PI'])
        for pi in PIs:
            m = (d['PI'] == pi); t = int(d['TEX'][m][0]); fl = int(d['FL'][m][0])
            if t not in noisetex or (fl & (1 | 2 | 4 | (1 << 24))): continue
            mm = m & ok
            if not mm.any(): continue
            w = area[mm]
            out.append(dict(pi=int(pi), tex=t, fl=fl, cell=int(d['CELL'][m][0]), area=float(w.sum()), Lu=wmedian(Lu[mm], w), Lv=wmedian(Lv[mm], w), ntri=int(m.sum())))
        res[name] = dict(sig=f'{sig:08x}', pieces=out, ntex=len(tex), noisetex=sorted(noisetex))
        A = np.array([p['area'] for p in out]); lu = np.array([p['Lu'] for p in out]); lv = np.array([p['Lv'] for p in out])
        g = np.sqrt(lu * lv)
        def q(x): return ' '.join(f'{wmedian(x, A) if p == 50 else float(np.percentile(x, p)):.2f}' for p in (5, 50, 95))
        print(f'{name} {sig:08x}: кусков с шумом {len(out)}, площадь {A.sum():.0f} м2; период по u (м/тайл) p5/мед/p95: {q(lu)}; по v: {q(lv)}; геом: {q(g)}; анизотропия median Lu/Lv {np.median(lu / lv):.2f}')
    if '--json' in sys.argv: Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(res))
main()
