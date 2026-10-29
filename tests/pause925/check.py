#!/usr/bin/env python3
"""№925 (Роб 24.10: «текст в меню паузы по-прежнему крупнее, чем я просил: размер как в Options, расстановку — как сейчас»).
  check.py PAUSE_RUN OPTIONS_RUN [--ref PAUSE_RUN_OLD] [--expect-fail]
Прогоны tests/pause925/pause.txt (shot pause_a) и tests/pause925/options.txt (shot opt_a, OPTIONS главного меню, FE).
  1. высота заглавных белых строк паузы (медиана, px на снимке) = высоте белых строк Options (VIEW MOVIES / VIEW CREDITS), допуск 0;
  2. число строк паузы не изменилось, шаг строк прежний (±1 px), низ букв каждой строки не сдвинулся против --ref (±1 px).
Код 0 — PASS; --expect-fail: 0 только если упало (красный: пакет ui.shr до №925, UI_TYPO_PAUSE925_OLD=1)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def bands(path, box, white_only):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)[box[1]:box[3], box[0]:box[2]]
    w = (a[..., 0] > 235) & (a[..., 1] > 235) & (a[..., 2] > 235)
    y = (a[..., 0] > 200) & (a[..., 1] > 180) & (a[..., 2] < 90)
    m = w if white_only else (w | y)
    rows = np.nonzero(m.sum(1) > 2)[0] + box[1]
    out, s, p = [], None, None
    for r in rows:
        if s is None: s = p = r
        elif r == p + 1: p = r
        else: out.append((int(s), int(p))); s = p = r
    if s is not None: out.append((int(s), int(p)))
    return out


def main():
    a = sys.argv[1:]; fail = '--expect-fail' in a; a = [x for x in a if x != '--expect-fail']
    ref = None
    if '--ref' in a: i = a.index('--ref'); ref = a[i + 1]; del a[i:i + 2]
    pr, orr = a[0], a[1]
    P = bands(Path(pr) / 'pause_a.png', (150, 60, 330, 250), False)
    F = [b for b in bands(Path(orr) / 'opt_a.png', (170, 110, 310, 170), True)]
    errs = []
    ph = float(np.median([e - s + 1 for s, e in P if (e - s + 1) >= 8])) if P else 0
    fh = float(np.median([e - s + 1 for s, e in F])) if F else 0
    print(f'  пауза: строк {len(P)}, высота {[e - s + 1 for s, e in P]}, низ {[e for s, e in P]}; Options: высота {[e - s + 1 for s, e in F]}')
    if not P or not F: errs.append('нет строк на снимке')
    elif ph != fh: errs.append(f'высота пауза {ph:.0f} px, Options {fh:.0f} px')
    if ref and P:
        R = bands(Path(ref) / 'pause_a.png', (150, 60, 330, 250), False)
        if len(R) != len(P): errs.append(f'число строк {len(P)} против {len(R)}')
        else:
            for k, ((s, e), (s0, e0)) in enumerate(zip(P, R)):
                if abs(e - e0) > 1: errs.append(f'строка {k}: низ {e} против {e0}')
    for e in errs: print('FAIL', e)
    ok = not errs
    if fail: ok = not ok
    print(('PASS' if not errs else 'FAIL') + ' · tests/pause925/check.py')
    sys.exit(0 if ok else 1)


main()
