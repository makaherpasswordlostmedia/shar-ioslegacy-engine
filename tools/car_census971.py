#!/usr/bin/env python3
"""№971/№972 перепись заливки машин NPC: по куску — сколько треугольников идёт заливкой (K), сколько остаётся текстурой, причина, яркость заливки.
  python3 tools/car_census971.py DATA_DIR [--csv out.csv]   (DATA_DIR — папка игры: traffic.shr, l2..l7/traffic.shr, msncars-lN.shr)"""
import sys, os
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import car_flat as C


def reason(p, r):
    if p['tex'] < 0: return 'без текстуры'
    if p['owner'] == 3: return 'вспышка/фара-плашка'
    if p['flags'] & C.PIECE_EXCL: return 'флаг: прозрачный/сложение/полосы'
    if not (p['flags'] & 16) or p['ni'] <= 0: return 'без индексов'
    if r is None: return 'мало ровных (<40%) или колесо со ступицей'
    return ''


def rows_of(label, f, tex, pieces, names):
    out = []
    for j, p in enumerate(pieces):
        r = C.piece_split(f, tex[p['tex']], p) if p['tex'] >= 0 else None
        ntri = p['ni'] // 3
        if r is None:
            out.append((label, names[j], j, p['wheel'], p['owner'], hex(p['flags']), ntri, 0, ntri, reason(p, r), -1, -1)); continue
        K, perm, cols = r
        cols2 = C.recolor956(names[j], p['wheel'], cols); a = np.array(cols2, float)
        out.append((label, names[j], j, p['wheel'], p['owner'], hex(p['flags']), ntri, K, ntri - K, 'частично' if K < ntri else 'целиком', float(a.mean()), float(a.max(1).min())))
    return out


def main():
    D = Path(sys.argv[1]); rows = []
    for lv in range(1, 8):
        t = D / 'traffic.shr' if lv == 1 else D / f'l{lv}' / 'traffic.shr'
        if t.exists():
            f, tex, models, pieces, _ = C.load_trf(t); nm = [''] * len(pieces)
            for m in models: nm[m['first']:m['first'] + m['n']] = [m['name']] * m['n']; nm[m['firstLod']:m['firstLod'] + m['nLod']] = [m['name']] * m['nLod']
            rows += rows_of(f'L{lv} трафик', f, tex, pieces, nm)
        m_ = D / f'msncars-l{lv}.shr' if (D / f'msncars-l{lv}.shr').exists() else D / f'l{lv}' / f'msncars-l{lv}.shr'
        if m_.exists():
            for name, f, tex, pieces in C.load_mcr(m_): rows += rows_of(f'L{lv} миссии', f, tex, pieces, [name] * len(pieces))
    if '--csv' in sys.argv:
        import csv
        with open(sys.argv[sys.argv.index('--csv') + 1], 'w', newline='') as o:
            w = csv.writer(o); w.writerow('набор модель кусок колесо owner флаги треуг заливка текстура вид яркость минимум'.split()); w.writerows(rows)
    tot = {}
    for r in rows:
        k = r[0]; a = tot.setdefault(k, [0, 0, 0, 0, 0]); a[0] += 1; a[1] += r[6]; a[2] += r[7]; a[3] += r[8]; a[4] += 1 if r[7] == 0 and r[6] > 0 else 0
    for k, a in tot.items(): print(f'{k:12s} кусков {a[0]:4d}, треуг {a[1]:6d}, заливкой {a[2]:6d} ({100 * a[2] / max(1, a[1]):.0f}%), текстурой {a[3]:6d}, кусков целиком текстурой {a[4]}')


if __name__ == '__main__': main()
