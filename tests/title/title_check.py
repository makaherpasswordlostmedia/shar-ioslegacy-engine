#!/usr/bin/env python3
"""№405/№409 — разбор прогона титульного экрана (tests/title/title.sh, сценарий tests/title/title_scenario.txt).

  title_check.py RUN_DIR [--expect-fail]

1) пульс «Press START button» (№405): строки TITLEPS (часы экрана, рамка надписи как ушла в GE) — ширина по времени
   подгоняется синусоидой; ждём период PS_P ± PS_P_TOL (запись PS2: 0,601 с), меньшая/большая PS_R ± PS_R_TOL (0,825),
   центр стоит (± CENTER_TOL px), наибольшая ширина — прежний размер порта (не шире рамки строки);
2) свечение логотипа (№409): tools/title_band.py по снимку title — сетка 4x4 не больше GRID_MAX, ровные полосы не длиннее
   FLAT_MAX px (ступени 5650 без дизеринга дают ~5,6 px, сетка дизеринга GE ~0,2–0,75).
Код 0 — PASS; --expect-fail: 0, только если упало (красный: -DTITLE_PULSE_OLD=1 -DTITLE_DITHER_OLD=1 и UI_LOGO_FS_OLD=1)."""
import argparse, re, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PS_P, PS_P_TOL, PS_R, PS_R_TOL, CENTER_TOL = .601, .02, .825, .02, .6
GRID_MAX, FLAT_MAX = .03, 2.5


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--expect-fail', action='store_true'); a = ap.parse_args()
    run = Path(a.run); errs = []; lines = []
    log = (run / 'smoke.txt').read_text(errors='replace') if (run / 'smoke.txt').exists() else ''
    rows = [tuple(float(v) for v in re.findall(r'=(-?[\d.]+)', l)) for l in log.splitlines() if l.startswith('TITLEPS ')]
    if len(rows) < 30: errs.append(f'строк TITLEPS {len(rows)} (титульный не показан?)')
    else:
        R = np.array(rows); t = R[:, 0]; w = R[:, 3] - R[:, 1]; cx = (R[:, 1] + R[:, 3]) / 2; cy = (R[:, 2] + R[:, 4]) / 2
        best = None
        for P in np.arange(.3, 1.2, .001):
            X = np.c_[np.ones_like(t), np.sin(2 * np.pi * t / P), np.cos(2 * np.pi * t / P)]; c = np.linalg.lstsq(X, w, rcond=None)[0]
            r = ((X @ c - w) ** 2).mean()
            if best is None or r < best[0]: best = (r, P, c)
        r, P, c = best; amp = float(np.hypot(c[1], c[2])); ratio = (c[0] - amp) / (c[0] + amp)
        lines.append(f'  пульс: кадров {len(t)}, ширина {w.min():.1f}..{w.max():.1f} px, период {P:.3f} с (PS2 {PS_P}), меньшая/большая '
                     f'{ratio:.3f} (PS2 {PS_R}), центр x {cx.min():.2f}..{cx.max():.2f}, y {cy.min():.2f}..{cy.max():.2f}')
        if amp < 1.: errs.append(f'надпись не пульсирует (ширина {w.min():.1f}..{w.max():.1f})')
        else:
            if abs(P - PS_P) > PS_P_TOL: errs.append(f'период {P:.3f} с')
            if abs(ratio - PS_R) > PS_R_TOL: errs.append(f'меньшая/большая {ratio:.3f}')
        if np.ptp(cx) > CENTER_TOL or np.ptp(cy) > CENTER_TOL: errs.append('центр надписи гуляет')
    shot = run / 'title.png'
    if not shot.exists(): errs.append('нет снимка title')
    else:
        out = subprocess.run([sys.executable, str(ROOT / 'tools/title_band.py'), str(shot)], capture_output=True, text=True).stdout
        m = re.search(r'кадр title\.png.*ровная полоса\s+([\d.]+) px\s+сетка 4x4 ([\d.]+)', out)
        lines += ['  ' + l for l in out.strip().splitlines()]
        if not m: errs.append('свечение логотипа не найдено на снимке')
        else:
            flat, grid = float(m.group(1)), float(m.group(2))
            if grid > GRID_MAX: errs.append(f'сетка 4x4 на свечении {grid:.3f} > {GRID_MAX}')
            if flat > FLAT_MAX: errs.append(f'ступени: ровная полоса {flat:.1f} px > {FLAT_MAX}')
    print(('PASS' if not errs else 'FAIL ' + '; '.join(errs)) + f' · tests/title/title_check.py {run.name}'); print('\n'.join(lines))
    if a.expect_fail: return 0 if errs else 1
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())
