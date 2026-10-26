#!/usr/bin/env python3
# лист «TEST70 / стало»: слева как в TEST70 (beam995 0), справа новое (beam995 1): вид сбоку, сверху, с земли, из машины в луче. sheet.py ДИР_ВЫХОДА выход.png
import sys
from PIL import Image, ImageDraw, ImageFont
d, out = sys.argv[1], sys.argv[2]
P = [('side', 'сбоку'), ('top', 'сверху'), ('low', 'с земли'), ('car', 'из машины в луче')]
W, H = 480, 272; sheet = Image.new('RGB', (W * 2, (H + 16) * len(P)), (20, 20, 20)); dr = ImageDraw.Draw(sheet); FT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
for i, (n, t) in enumerate(P):
    y = i * (H + 16)
    for j, (tag, cap) in enumerate((('off', 'TEST70'), ('on', 'стало'))):
        try: sheet.paste(Image.open(f'{d}/b995_{n}_{tag}.bmp').convert('RGB'), (j * W, y + 16))
        except Exception: pass
        dr.text((j * W + 4, y + 3), f'{t}  {cap}', fill=(255, 255, 255), font=FT)
sheet.save(out)
