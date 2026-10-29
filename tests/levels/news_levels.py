#!/usr/bin/env python3
"""Сверка газет уровней 1..7 (tests/levels/news_levels.sh): кадр news_2s каждого входа (RESUME / NEW) против loadingN.png с диска.
  news_levels.py ПАПКА_РЕЗУЛЬТАТОВ [--expect-wrong N]   -> строка PASS/FAIL, лист ПАПКА/news_levels_sheet.png
Вход: ПАПКА/disk/loadingN.png, ПАПКА/res/<resume|new>_N/news_2s.png и smoke.txt (LOADNEWS idx=… — газета ПЕРВОГО кадра).
Пятно газеты (108,29)-(371,213) сравнивается нормированной корреляцией со всеми семью дисковыми; верно, если лучший — тот же N."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
BOX = (108, 29, 371, 213)

def vec(im):
    a = np.asarray(im.convert('L').resize((BOX[2] - BOX[0], BOX[3] - BOX[1])), dtype=np.float64).ravel()
    a -= a.mean(); n = np.linalg.norm(a); return a / n if n else a

def main():
    root = Path(sys.argv[1]); wrong = 'N'
    disk = {n: Image.open(root / 'disk' / f'loading{n}.png').convert('RGB') for n in range(1, 8)}
    dv = {n: vec(im) for n, im in disk.items()}
    rows, bad = [], []
    for n in range(1, 8):
        row = [disk[n]]
        for kind in ('resume', 'new'):
            d = root / 'res' / f'{kind}_{n}'; p = d / 'news_2s.png'
            if not d.exists(): row.append(None); continue   # уровень не гонялся (LEVELS=...)
            if not p.exists(): bad.append(f'{kind} L{n}: нет кадра'); row.append(None); continue
            im = Image.open(p).convert('RGB'); row.append(im)
            v = vec(im.crop(BOX)); sc = {k: float(v @ dv[k]) for k in dv}; best = max(sc, key=sc.get)
            s = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
            idx = next((int(l.split('idx=')[1].split()[0]) for l in s.splitlines() if l.startswith('LOADNEWS')), -1)
            tag = f'{kind} L{n}: лучший диск={best} (корр {sc[best]:.2f}, свой {sc[n]:.2f}), первый кадр idx={idx}'
            if best != n or idx != n - 1: bad.append('НЕ ТА ГАЗЕТА ' + tag)
            print(tag)
        rows.append(row)
    W, H = 320, 181; sh = Image.new('RGB', (W * 3, (H + 16) * 7 + 16), (24, 24, 24)); dr = ImageDraw.Draw(sh)
    dr.text((4, 2), 'disk loadingN.png | port RESUME at level N | port NEW / level change N', fill=(255, 255, 255))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            if im: sh.paste(im.resize((W, H)), (c * W, 16 + r * (H + 16) + 14))
        dr.text((4, 16 + r * (H + 16)), f'L{r + 1}', fill=(255, 255, 0))
    sh.save(root / 'news_levels_sheet.png')
    print('FAIL: ' + '; '.join(bad) if bad else 'PASS: газета каждого уровня верна на обоих входах'); return 1 if bad else 0

if __name__ == '__main__': raise SystemExit(main())
