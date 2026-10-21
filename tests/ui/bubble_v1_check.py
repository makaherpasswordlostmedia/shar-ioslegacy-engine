#!/usr/bin/env python3
"""Принцип пузыря v1 (Роб 17.10; память project_shar_bubble_law): по кадрам tests/ui/b689_msgs_scenario.txt (7 видов сообщений).
   bubble_v1_check.py DIR [--expect-old]
   1. ни одной буквы на территории скругления: буквы x ∈ [рамка + R, рамка + ширина − R], R = половина высоты рамки (по ободу);
   2. высота рамки постоянная у всех видов (±1 px) — пузырь растёт только в ширину;
   3. правый край рамки ≤ 341 (обод радара 387 − 2 × 23);
   4. текст у верха: поле сверху одно у всех (±2 px); снизу не меньше верхнего − 1.
   Красный контроль: кадры TEST31 до v1 — буквы в скруглении и рамка выше родной."""
import sys
import numpy as np
from PIL import Image
NAMES = ('a_talk', 'b_dest', 'c_m2', 'd_m3', 'e_m5', 'f_m6', 'g_long')


def frame(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)[150:272, 0:400]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rim = (r > 200) & (g > 180) & (b > 100) & (b < 210)
    rows = np.nonzero(rim[:, 62:].sum(1) > 40)[0]
    if len(rows) < 2: return None
    y0, y1 = rows.min(), rows.max()
    while y0 > 0 and rim[y0 - 1, 62:].sum() > 10: y0 -= 1
    while y1 < rim.shape[0] - 1 and rim[y1 + 1, 62:].sum() > 10: y1 += 1
    cols = np.nonzero(rim[y0:y1 + 1].any(0))[0]; x1 = cols.max()
    mid = (y0 + y1) // 2; xl = np.nonzero(rim[mid, :])[0]; x0 = xl.min()   # левый край по средней строке (у аватарки — кольцо аватара левее: берём первый обод правее 62, если есть аватар)
    av = rim[mid, :62].any() and (rim[mid, 62:120].any())
    if av: x0 = 62 + np.nonzero(rim[mid, 62:])[0].min()
    top_rim = [y for y in range(y0, mid) if rim[y, (x0 + x1) // 2]]; bot_rim = [y for y in range(mid, y1 + 1) if rim[y, (x0 + x1) // 2]]
    yi0, yi1 = max(top_rim), min(bot_rim)
    near = rim.copy()
    for dy in (-2, -1, 1, 2):
        near |= np.roll(rim, dy, 0)
    for dx in (-3, -2, -1, 1, 2, 3):
        near |= np.roll(rim, dx, 1)
    txt = (r > 200) & (g > 200) & (b < 90) & ~near; txt[:, :x0 + 2] = False   # жёлтые буквы, не золото обода
    txt[:, x1 - 5:] = False                                         # блик внутреннего края обода справа — не буква
    ty, tx = np.nonzero(txt[yi0 + 1:yi1, :x1])
    if not len(ty): return None
    H = y1 - y0 + 1; R = H / 2
    return dict(x0=int(x0), x1=int(x1), H=int(H), R=R, av=bool(av), tl=int(tx.min()), tr=int(tx.max()), top=int(ty.min()), bot=int((yi1 - yi0 - 2) - ty.max()))


if __name__ == '__main__':
    d = sys.argv[1]; bad = []
    F = {n: frame('%s/%s.png' % (d, n)) for n in NAMES}
    for n, f in F.items():
        if f is None: bad.append(n + ': рамка/текст не найдены'); continue
        left_ok = f['av'] or f['tl'] >= f['x0'] + f['R'] - 1
        right_ok = f['tr'] <= f['x1'] - f['R'] + 1
        print('  %-7s рамка x%d..%d h%d R%.0f %s | буквы x%d..%d | сверху %d снизу %d' % (n, f['x0'], f['x1'], f['H'], f['R'], 'аватар' if f['av'] else '', f['tl'], f['tr'], f['top'], f['bot']))
        if not left_ok: bad.append(n + ': буквы в левом скруглении')
        if not right_ok: bad.append(n + ': буквы в правом скруглении')
        if f['x1'] > 341: bad.append(n + ': правый край рамки %d > 341 (радар)' % f['x1'])
        if f['bot'] < f['top'] - 1 and n != 'g_long': bad.append(n + ': снизу меньше, чем сверху')
    ok_f = [f for f in F.values() if f]
    if ok_f:
        hs = [f['H'] for f in ok_f if not f['av']]; ha = [f['H'] for f in ok_f if f['av']]
        for grp, nm in ((hs, 'без аватара'), (ha, 'с аватаром')):
            if grp and max(grp) - min(grp) > 1: bad.append('высота рамки %s гуляет %s' % (nm, sorted(set(grp))))
        xr = [f['x1'] for f in ok_f]   # Роб 17.10 вечер: один формат — правый край рамки у всех один (BUB_ONE_RIGHT)
        if max(xr) - min(xr) > 2: bad.append('ширина пузырей разная: правый край %s' % sorted(set(xr)))
        tops = [f['top'] for n, f in F.items() if f and n != 'g_long' and not f['bot'] <= f['top'] + 1]   # впритык (много строк: поля сверху = снизу) — своя градация закона
        if tops and max(tops) - min(tops) > 2: bad.append('поле сверху разное %s' % sorted(set(tops)))
    for b in bad: print('FAIL', b)
    ok = not bad
    if '--expect-old' in sys.argv: ok = not ok
    print('PASS bubble_v1' if not bad else 'FAIL bubble_v1 (%d)' % len(bad)); sys.exit(0 if ok else 1)
