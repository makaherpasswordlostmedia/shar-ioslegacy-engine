#!/usr/bin/env python3
"""№954: сравнение кадров прогона sky_l6.txt: ОЛД (SKY954_OLD=1) против НОВОГО. Читает out_old/out_new (png 480×272), служебная строка и миникарта не считаются (y < 36, правый нижний круг).
  shots.py OLD_DIR NEW_DIR [--expect-change]   последняя строка PASS/FAIL
  L6 (кадры s6_*): новый отличается от прежнего (небо стало градиентом + звёзды): ≥ 1500 пикселей с разницей > 12 в сумме кадров; средняя разница по кадру ≤ 14 (картинка узнаётся: тон и яркость горизонта держатся)
  L2/L5/L4 (s2_*, s5_*, s4_*): картинка не расходится: средняя разница ≤ 6 по каждому кадру (градиентный купол и облака остаются прежними)
  без --expect-change проверка «отличается» не нужна (красный контроль: ОЛД против ОЛД обязан не пройти её)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

def load(d, n):
    a = np.array(Image.open(Path(d) / (n + '.png')).convert('RGB')).astype(int)
    m = np.ones(a.shape[:2], bool); m[:36] = False
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]; m &= ~((xx - 420) ** 2 + (yy - 215) ** 2 < 55 ** 2)
    return a, m

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; exp = '--expect-change' in sys.argv
    od, nd = a[0], a[1]; ok = True; big = 0
    for n in sorted(p.stem for p in Path(nd).glob('s[2456]_*.png')):
        if not (Path(od) / (n + '.png')).exists(): print('нет', n, 'в', od); ok = False; continue
        o, m = load(od, n); w, _ = load(nd, n); d = np.abs(o - w).max(-1)[m]; mean = np.abs(o - w).mean(-1)[m].mean(); nb = int((d > 12).sum())
        lim = 14 if n.startswith('s6') else 6
        if n.startswith('s6'): big += nb
        good = mean <= lim; ok &= good
        print('%-12s средняя разница %.2f (≤ %d) пикселей >12: %d %s' % (n, mean, lim, nb, 'ok' if good else 'ПАДАЕТ'))
    if exp:
        ch = big >= 1500; ok &= ch; print('L6 изменился: пикселей >12 всего %d (≥ 1500) %s' % (big, 'ok' if ch else 'ПАДАЕТ'))
    print('PASS' if ok else 'FAIL'); return 0 if ok else 1

sys.exit(main())
