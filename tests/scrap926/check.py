#!/usr/bin/env python3
"""№926 (Роб 24.10: «в Scrapbook слева внизу LEVEL и L/R, но там стоит знак (вопросительный?); нужно просто писать номер уровня»).
  check.py RUN_DIR [--expect-fail]     RUN_DIR — прогон tests/scrap926/scenario.txt (кадры sb_l1 и sb_l7: страница L1 и по L — страница L7)
Подпись слева внизу: «LEVEL N» (белая) и «L / R» (серая). Нет граней цифр и «/» в атласе шрифта — на их месте запасной знак «?» (одна и та же картинка у всех).
  1. подпись читается: 5 белых букв, цифра, 3 серых знака;
  2. цифра на кадре L1 и на кадре L7 — разные картинки (были одинаковым «?»);
  3. цифра и «/» — не одна картинка (оба были «?»); буква V отличается от E.
Код 0 — PASS; --expect-fail: 0, только если упало (красный: пакет ui.shr с SCRAP926_OLD=1)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

BOX = (16, 238, 200, 268)


def blobs(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)[BOX[1]:BOX[3], BOX[0]:BOX[2]]
    mx, mn = a.max(2), a.min(2)
    low = (mx - mn) < 26
    white = low & (mn > 215); gray = low & (mn >= 150) & (mx <= 186)
    wx = np.nonzero(white.sum(0))[0]
    if len(wx): gray[:, :wx.max() + 4] = False; gray[:, wx.max() + 70:] = False   # серая «L / R» — правее «LEVEL N», рядом
    out = []
    for name, m in (('w', white), ('g', gray)):
        cols = np.nonzero(m.sum(0) > 0)[0]; s = p = None; segs = []
        for c in cols:
            if s is None: s = p = c
            elif c <= p + 1: p = c          # соседние столбцы — одна буква (просвет между буквами 1 px и больше)
            else: segs.append((s, p)); s = p = c
        if s is not None: segs.append((s, p))
        for s, e in segs:
            sub = m[:, s:e + 1]; r = np.nonzero(sub.any(1))[0]
            out.append((name, s + BOX[0], sub[r.min():r.max() + 1].astype(np.uint8)))
    return sorted(out, key=lambda b: b[1])


def same(a, b):
    return a.shape == b.shape and (a == b).all()


def main():
    run = Path(sys.argv[1]); fail = '--expect-fail' in sys.argv; errs = []
    B1, B7 = blobs(run / 'sb_l1.png'), blobs(run / 'sb_l7.png')
    for nm, B in (('L1', B1), ('L7', B7)):
        w = [b for b in B if b[0] == 'w']; g = [b for b in B if b[0] == 'g']
        print(f'  {nm}: белых знаков {len(w)}, серых {len(g)}')
        if len(w) != 6 or len(g) != 3: errs.append(f'{nm}: знаков {len(w)} белых и {len(g)} серых (ждали 6 и 3)')
    if not errs:
        w1 = [b[2] for b in B1 if b[0] == 'w']; w7 = [b[2] for b in B7 if b[0] == 'w']; g1 = [b[2] for b in B1 if b[0] == 'g']
        if same(w1[5], w7[5]): errs.append('цифра на L1 и L7 одна и та же картинка (запасной знак)')
        if same(w1[5], g1[1]): errs.append('цифра и «/» — одна картинка (запасной знак)')
        if same(w1[2], w1[1]): errs.append('V и E — одна картинка')
    for e in errs: print('FAIL', e)
    ok = not errs
    if fail: ok = not ok
    print(('PASS' if not errs else 'FAIL') + ' · tests/scrap926/check.py')
    sys.exit(0 if ok else 1)


main()
