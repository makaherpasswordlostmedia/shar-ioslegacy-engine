#!/usr/bin/env python3
"""Лавка: название машины не заходит под счёт монет (TITLE_COINS_FIT_OLD), у счёта есть монета (SHOP_COIN3D_OLD).
   title_coins_check.py DIR  — кадры t0..t2 сценария tests/shop/title_coins_scenario.txt (t1 — Surveillance Van, 2000 монет).
   В полосе y 14..42 справа от центра: просвет между названием и цифрами счёта не меньше GAP.
   Красный контроль — кадры движка с TITLE_COINS_FIT_OLD=1 / прежнего TEST30: просвета нет."""
import sys
import numpy as np
from PIL import Image
GAP = 6    # TITLE_COINS_GAP 8 минус сглаживание краёв букв; монета у счёта справа от цифр (№672, COIN_RIGHT_OLD)


def ink(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)[14:42, 240:440]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return ((r > 200) & (g > 195) & (b < 120)).sum(0) > 0       # столбцы с ярко-жёлтым: буквы и цифры (монета оранжевее и вращается — не считается)


def count_left(cols):
    """кадр t0 (Duff Truck — название короткое): самый длинный пустой промежуток отделяет название от счёта; -> левый столбец счёта"""
    best, run, start = (0, None), 0, None
    for x, c in enumerate(cols):
        if not c:
            if run == 0: start = x
            run += 1
        else:
            if run > best[0] and start is not None and start > 0: best = (run, x)
            run = 0
    return best[1]


def gap(d):
    cl = count_left(ink(d + '/t0.png'))
    c1 = ink(d + '/t1.png')
    left = np.nonzero(c1[:cl])[0]
    return (cl - 1 - left.max()) if len(left) else 99, cl + 240


if __name__ == '__main__':
    g, cl = gap(sys.argv[1])
    ok = g >= GAP
    print('Surveillance Van: счёт с x=%d, просвет до него %d px (нужно >= %d): %s' % (cl, g, GAP, 'OK' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)
