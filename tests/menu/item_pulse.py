#!/usr/bin/env python3
"""Гейт правки 412 по прогону tests/menu/item_pulse.txt (строки MENUITEM: рамка выбранного пункта главного меню, как ушла в GE).
  item_pulse.py RUN_DIR [--expect-fail]
Числа диска (SLES_518.97, CGuiMenu 0x1a6eb8 / 0x1e7b58): масштаб 1,05 + 0,1·sin(2π t/600 мс − π/6), фаза с нуля на смене пункта.
Мерим по ширине строки (подгонка синусоиды по каждому пункту отдельно): период 0,600 ± 0,02 с, меньшая/большая 0,826 ± 0,02,
центр стоит (± 0,6 px), наибольшая ширина — строка порта (± 1 px), на первом кадре после смены пункта ширина = 1/1,15 наибольшей
(± 0,02), правый край не заходит на стрелку (x1 < 307). Код 0 — PASS; --expect-fail: 0, только если упало (-DMENU_PULSE_OLD=1)."""
import argparse, math, re, sys
from pathlib import Path
import numpy as np
P0, R0, ARROW_X = .600, (1.05 - .1) / (1.05 + .1), 307.


def fit(t, w):
    best = None
    for P in np.arange(.3, 1.2, .001):
        X = np.c_[np.ones_like(t), np.sin(2 * np.pi * t / P), np.cos(2 * np.pi * t / P)]; c = np.linalg.lstsq(X, w, rcond=None)[0]
        r = ((X @ c - w) ** 2).mean()
        if best is None or r < best[0]: best = (r, P, c)
    r, P, c = best; a = float(np.hypot(c[1], c[2])); return P, (c[0] - a) / (c[0] + a), a


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--expect-fail', action='store_true'); a = ap.parse_args()
    rows = [dict((k, float(v)) for k, v in re.findall(r'(\w+)=(-?[\d.]+)', l)) for l in
            (Path(a.run) / 'smoke.txt').read_text(errors='replace').splitlines() if l.startswith('MENUITEM ')]
    errs = []
    sels = sorted({int(r['sel']) for r in rows})
    if len(rows) < 60 or len(sels) < 2: errs.append(f'строк MENUITEM {len(rows)}, пунктов {sels} (меню не показано / пункт не сменился)')
    for sel in sels:
        R = [r for r in rows if int(r['sel']) == sel]
        t = np.array([r['t'] for r in R]); w = np.array([r['x1'] - r['x0'] for r in R]); cx = np.array([(r['x0'] + r['x1']) / 2 for r in R])
        cy = np.array([(r['y0'] + r['y1']) / 2 for r in R])
        P, ratio, amp = fit(t - t[0], w)
        first = w[0] / w.max() if len(w) else 0
        print(f'  пункт {sel}: кадров {len(t)}, ширина {w.min():.1f}..{w.max():.1f} px, период {P:.3f} с (диск {P0}), меньшая/большая {ratio:.3f} '
              f'(диск {R0:.3f}), первый кадр {first:.3f} наибольшей (диск {1 / 1.15:.3f}), центр x {np.ptp(cx):.2f} y {np.ptp(cy):.2f} px, '
              f'правый край до {max(r["x1"] for r in R):.1f} (стрелка {ARROW_X:.0f})')
        if len(t) < 30: errs.append(f'пункт {sel}: мало кадров'); continue
        if amp < 1.: errs.append(f'пункт {sel} не пульсирует'); continue
        if abs(P - P0) > .02: errs.append(f'пункт {sel}: период {P:.3f}')
        if abs(ratio - R0) > .02: errs.append(f'пункт {sel}: меньшая/большая {ratio:.3f}')
        if abs(first - 1 / 1.15) > .02: errs.append(f'пункт {sel}: фаза на смене пункта {first:.3f}')
        if np.ptp(cx) > .6 or np.ptp(cy) > .6: errs.append(f'пункт {sel}: центр гуляет')
        if max(r['x1'] for r in R) >= ARROW_X: errs.append(f'пункт {sel}: наезд на стрелку')
    print(('PASS' if not errs else 'FAIL ' + '; '.join(errs)) + f' · tests/menu/item_pulse.py {Path(a.run).name}')
    return (0 if errs else 1) if a.expect_fail else (0 if not errs else 1)


if __name__ == '__main__':
    sys.exit(main())
