#!/usr/bin/env python3
"""Гейт правки 413 (хвост): пульс выбранного пункта на меню, где SLES_518.97 создаёт CGuiMenu с флагами 2 (tests/menu/pulse_all.txt).
По строкам MENUITEM (us — часы PSP, scr/mode — экран, sel — пункт, рамка строки): по каждому отрезку одного пункта не короче
MIN_FR кадров подгоняется синусоида ширины — период 0,600 ± 0,02 с, меньшая/большая 0,826 ± 0,02 (числа 0x1e7b58: 1,05 ± 0,1).
Ждём: пауза миссии (scr 6, основной пакет), OPTIONS паузы (scr 0, pmenu), SOUND (scr 1, pmenu); SETTINGS (scr 2, pmenu,
флаги 0) — ни одной строки. --expect-fail: 0, только если упало (красный -DMENU_PULSE_OLD=1).
  pulse_all.py RUN_DIR [--expect-fail]"""
import re, sys
from pathlib import Path
import numpy as np
P0, R0, MIN_FR = .600, .95 / 1.15, 30
NEED = {(6, 0): 'пауза миссии (PauseMission)', (0, 1): 'OPTIONS паузы (PauseOptions)', (1, 1): 'SOUND (Sound)'}
NONE = {(2, 1): 'SETTINGS (PauseSettings, флаги 0)'}


def fit(t, w):
    best = None
    for P in np.arange(.3, 1.2, .001):
        X = np.c_[np.ones_like(t), np.sin(2 * np.pi * t / P), np.cos(2 * np.pi * t / P)]; c = np.linalg.lstsq(X, w, rcond=None)[0]
        r = ((X @ c - w) ** 2).mean()
        if best is None or r < best[0]: best = (r, P, c)
    r, P, c = best; a = float(np.hypot(c[1], c[2])); return P, (c[0] - a) / (c[0] + a), a


rows = [dict((k, float(v)) for k, v in re.findall(r'(\w+)=(-?[\d.]+)', l)) for l in
        (Path(sys.argv[1]) / 'smoke.txt').read_text(errors='replace').splitlines() if l.startswith('MENUITEM ') and 'us=' in l]
errs = []
for key, name in NEED.items():
    R = [r for r in rows if (int(r['scr']), int(r['mode'])) == key]
    segs = {}
    for r in R: segs.setdefault(int(r['sel']), []).append(r)
    seg = max(segs.values(), key=len) if segs else []
    if len(seg) < MIN_FR: errs.append(f'{name}: строк {len(seg)}'); print(f'  {name}: строк {len(seg)}'); continue
    t = (np.array([r['us'] for r in seg]) - seg[0]['us']) * 1e-6; w = np.array([r['x1'] - r['x0'] for r in seg])
    P, ratio, amp = fit(t, w)
    print(f'  {name}: пункт {int(seg[0]["sel"])}, кадров {len(seg)}, ширина {w.min():.1f}..{w.max():.1f}, период {P:.3f} с (диск {P0}), '
          f'меньшая/большая {ratio:.3f} (диск {R0:.3f})')
    if amp < 1. or abs(P - P0) > .02 or abs(ratio - R0) > .02: errs.append(f'{name}: не тот пульс')
for key, name in NONE.items():
    n = sum((int(r['scr']), int(r['mode'])) == key for r in rows)
    print(f'  {name}: строк {n} (нужно 0)')
    if n: errs.append(f'{name}: пульс там, где у оригинала его нет')
print(('PASS' if not errs else 'FAIL ' + '; '.join(errs)) + f' · tests/menu/pulse_all.py {Path(sys.argv[1]).name}')
sys.exit((0 if errs else 1) if '--expect-fail' in sys.argv else (0 if not errs else 1))
