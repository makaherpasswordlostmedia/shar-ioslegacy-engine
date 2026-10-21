#!/usr/bin/env python3
"""№732 (Роб 17.10: лучи гардероба по центру экрана и их меньше): запечённый фон tools/wardrobe_rays.py.
   Зелёное: центр клиньев в середине экрана (240, 136), клиньев 12. Красный контроль: WARDROBE_RAYS732_OLD=1 — центр у ног (y ≈ 216), 16 клиньев.
   python3 tests/shop/wardrobe_rays732.py [--expect-old]  -> код 0/1"""
import math, os, subprocess, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def wedges(m, cx, cy, r):
    T = np.linspace(0, 2 * math.pi, 1440, endpoint=False)
    yy = np.rint(cy + r * np.sin(T)).astype(int); xx = np.rint(cx + r * np.cos(T)).astype(int)
    if yy.min() < 0 or yy.max() > 271: return -1
    ring = m[yy, xx]; return int((ring & ~np.roll(ring, 1)).sum())


def check(cy, n):
    """клиньев n на трёх окружностях (r 15, 30, 50) вокруг (240, cy) — так бывает только у настоящего центра"""
    import wardrobe_rays as WR
    _, m = WR.bake([90, 99, 180], [37, 43, 67], (240.0, 134.0, 183.0))
    got = [wedges(m, 240, cy, r) for r in (15, 30, 50) if cy + r < 272]
    return got, all(g == n for g in got)


if __name__ == '__main__':
    old = '--expect-old' in sys.argv
    cy, n = (int(134 + 183 * .45), 16) if old else (136, 12)
    got, ok = check(cy, n)
    print('лучи вокруг (240, %d): клиньев на окружностях %s, ждали %d: %s' % (cy, got, n, 'OK' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)
