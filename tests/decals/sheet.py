#!/usr/bin/env python3
"""Лист было/стало плоских деталей уровня 1 (правки Роба 37, 43) из двух прогонов эмулятора tests/decals/emu.sh.

    python tests/decals/sheet.py ДО_папка ПОСЛЕ_папка [--out build/decals/sheet.png]

Папки — итог tools/smoke.sh (снимки окна <место>_a.png и <место>_b.png, через 0.5 с). На листе по строке на место:
до | после (снимок a) и крупно деталь до | после. Мерцание: машина и камера стоят, поэтому пиксели мира, изменившиеся
между a и b больше чем на DIFF_MIN по яркости, — мигание слоёв/швов или живое (пешеходы, трафик, листва), поэтому
сравнивается до/после, а не с нулём. Заголовок окна и HUD не в счёт. Эмулятор на Маке пишет глубину точнее 16 бит PSP,
так что мигание слоёв вдали он почти не показывает — лист проверяет, что детали на месте и целы (ничего не спрятано
отсечением, не срезано), а разведение слоёв по глубине доказывают tools/seams.py и tools/decals.py."""
import argparse, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# место, подпись, рамка детали (доли снимка окна: x0, y0, x1, y1)
SPOTS = [('house', 'улица у дома Симпсонов (≈50 м)', (0.00, 0.38, 0.50, 0.62)),
         ('road', 'разметка у дома', (0.45, 0.35, 0.95, 0.65)),
         ('school', 'вывеска SCHOOL', (0.42, 0.10, 0.58, 0.30)),
         ('kwik', 'вывеска Kwik-E-Mart', (0.26, 0.10, 0.55, 0.30)),
         ('mat', 'коврик Welcome', (0.30, 0.47, 0.46, 0.60))]
DIFF_MIN = 24
FONTS = ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf')


def font(size):
    for f in FONTS:
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()


def world_mask(w, h):
    """мир без заголовка окна и HUD (радар справа внизу, счётчики вверху справа)"""
    m = np.zeros((h, w), bool)
    m[int(h * .12):int(h * .72), int(w * .06):int(w * .78)] = True
    return m


def flicker(a, b):
    A = np.asarray(a.convert('L'), np.int16); B = np.asarray(b.convert('L').resize(a.size), np.int16)
    return float((np.abs(A - B)[world_mask(*a.size)] > DIFF_MIN).mean())


def crop(im, box):
    w, h = im.size; x0, y0, x1, y1 = box
    return im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('before'); ap.add_argument('after')
    ap.add_argument('--out', default='build/decals/sheet.png')
    a = ap.parse_args()
    dirs = [Path(a.before), Path(a.after)]
    rows, table = [], []
    for key, title, box in SPOTS:
        ims, fl = [], []
        for d in dirs:
            pa, pb = d / f'{key}_a.png', d / f'{key}_b.png'
            if not pa.exists(): ims.append(None); fl.append(None); continue
            im = Image.open(pa).convert('RGB'); ims.append(im)
            fl.append(flicker(im, Image.open(pb).convert('RGB')) if pb.exists() else None)
        rows.append((title, ims, fl, box)); table.append((key, fl))
    w, h = 384, 230; cw = 300; pad = 30; f1, f2 = font(15), font(20)
    sheet = Image.new('RGB', (2 * w + 2 * cw + 5 * 8, len(rows) * (h + pad) + 50), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, t in enumerate(('ДО (main a7305b4)', 'ПОСЛЕ (правки 37/43)', 'деталь: до', 'деталь: после')):
        x = 8 + (i * (w + 8) if i < 2 else 2 * (w + 8) + (i - 2) * (cw + 8))
        dr.text((x, 12), t, fill=(235, 235, 235), font=f2)
    y = 46
    for title, ims, fl, box in rows:
        for i, im in enumerate(ims):
            x = 8 + i * (w + 8)
            lab = f'{title}: мерцание {fl[i] * 100:.2f}% пикс.' if fl[i] is not None else f'{title}: нет снимка'
            dr.text((x, y), lab, fill=(255, 220, 120), font=f1)
            if im is None: continue
            sheet.paste(im.resize((w, h)), (x, y + 20))
            c = crop(im, box); ch = h; cwid = min(cw, int(c.size[0] * ch / max(c.size[1], 1)))
            sheet.paste(c.resize((cwid, ch)), (8 + 2 * (w + 8) + i * (cw + 8), y + 20))
        y += h + pad
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); sheet.save(out)
    print('место        до       после   (доля пикселей мира, изменившихся за 0.5 с при стоящей камере)')
    for key, fl in table:
        print(f'{key:8} ' + '  '.join(f'{v * 100:7.2f}%' if v is not None else '    нет ' for v in fl))
    print('лист:', out)


if __name__ == '__main__':
    sys.exit(main())
