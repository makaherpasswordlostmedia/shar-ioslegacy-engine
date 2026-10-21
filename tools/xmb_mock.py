#!/usr/bin/env python3
"""Макет меню PSP (XMB) в масштабе экрана 480×272: фон PIC1 + наша иконка ICON0 в фокусе, как на видео Роба
(IMG_7656.MOV 0:13–0:34: столбец значков слева, наша плитка 144×80 в фокусе у x≈20, y≈100, соседние значки меньше,
часы справа сверху). «Было / стало» рядом и иконка ×3 — для правки Роба 30 (картинки EBOOT: tools/icon0.py, tools/pic1.py).
Соседние значки — серые плашки-заглушки (чужие игры в макет не кладём).
  tools/xmb_mock.py --before-icon A.png --before-pic1 B.png [--icon build/assets/icon0.png] [--pic1 build/assets/pic1.png]
                    [--out build/ui_shots/xmb/xmb_30.png]"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--before-icon', required=True); ap.add_argument('--before-pic1', required=True)
ap.add_argument('--icon', default=str(ROOT / 'build/assets/icon0.png')); ap.add_argument('--pic1', default=str(ROOT / 'build/assets/pic1.png'))
ap.add_argument('--out', default=str(ROOT / 'build/ui_shots/xmb/xmb_30.png'))
ap.add_argument('--after-label', default='СТАЛО: фон на 28 px правее, v.0.1 и PSP от края плашки HIT&RUN')
a = ap.parse_args()
FOCUS = (20, 100)                                   # левый верх плитки в фокусе (по видео, экран 480×272)
try:
    FONT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)   # подписи макета (кириллица)
except OSError:
    FONT = ImageFont.load_default()


def xmb(pic1, icon):
    im = Image.open(pic1).convert('RGBA').resize((480, 272))
    d = ImageDraw.Draw(im, 'RGBA')
    # правка 132: столбец значков по видео Роба IMG_7656.MOV 0:20 — экранный x ~20..170 (прежде заглушки 45..125 были уже)
    d.rounded_rectangle((26, 30, 158, 92), 3, fill=(210, 215, 230, 200))          # значок выше (заглушка)
    d.rounded_rectangle((26, 188, 158, 248), 3, fill=(210, 215, 230, 200))        # значок ниже (заглушка)
    d.rounded_rectangle((26, 254, 158, 272), 3, fill=(210, 215, 230, 160))
    ic = Image.open(icon).convert('RGBA')
    im.alpha_composite(ic, FOCUS)
    x, y = FOCUS; d.rounded_rectangle((x - 2, y - 2, x + 145, y + 81), 5, outline=(255, 255, 255, 230), width=2)   # рамка фокуса XMB
    d.text((392, 6), '9/28 20:33', fill=(255, 255, 255, 230))
    return im.convert('RGB')


b = xmb(a.before_pic1, a.before_icon); n = xmb(a.pic1, a.icon)
ib = Image.open(a.before_icon).convert('RGB').resize((432, 240), Image.NEAREST)
inn = Image.open(a.icon).convert('RGB').resize((432, 240), Image.NEAREST)
out = Image.new('RGB', (480 * 2 + 12, 272 + 12 + 240 + 24), (40, 40, 40))
d = ImageDraw.Draw(out)
out.paste(b, (0, 0)); out.paste(n, (492, 0))
out.paste(ib, (24, 290)); out.paste(inn, (516, 290))
d.text((4, 274), 'БЫЛО (меню PSP 1:1, внизу иконка ×3)', fill=(230, 230, 230), font=FONT)
d.text((496, 274), a.after_label, fill=(230, 230, 230), font=FONT)
Path(a.out).parent.mkdir(parents=True, exist_ok=True); out.save(a.out)
print(a.out, out.size)
