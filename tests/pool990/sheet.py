#!/usr/bin/env python3
# лист «TEST70 / стало»: слева как в TEST70 (pool990 0), справа новое (pool990 1), по строке на место. sheet.py out_dir выход.png  — печатает среднюю разницу кадров по месту
import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np
d, out = sys.argv[1], sys.argv[2]
P = [('l1', 'L1 улица'), ('l4', 'L4 день'), ('l5s', 'L5 улица'), ('l5b', 'L5 мост'), ('l6p', 'L6 причал'), ('l7n', 'L7 ночь'), ('l3', 'L3')]
W, H = 480, 272; sheet = Image.new('RGB', (W * 2, (H + 16) * len(P)), (20, 20, 20)); dr = ImageDraw.Draw(sheet); FT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
for i, (n, t) in enumerate(P):
    try: a = Image.open(f'{d}/p990_{n}_off.bmp').convert('RGB'); b = Image.open(f'{d}/p990_{n}_on.bmp').convert('RGB')
    except Exception: continue
    y = i * (H + 16); sheet.paste(a, (0, y + 16)); sheet.paste(b, (W, y + 16))
    df = float(np.abs(np.asarray(a, float) - np.asarray(b, float))[40:, :].mean()); dr.text((4, y + 3), f'{t}  TEST70', fill=(255, 255, 255), font=FT); dr.text((W + 4, y + 3), f'{t}  стало (разница {df:.2f})', fill=(255, 255, 255), font=FT)
    print(f'{n}: разница кадров {df:.2f}')
sheet.save(out)
