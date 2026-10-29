#!/usr/bin/env python3
# №791: лист «до | после» по снимкам двух прогонов эмулятора: sheet.py ДО ПОСЛЕ OUT.png снимок1 снимок2 …
import sys, os
from PIL import Image, ImageDraw, ImageFont
a, b, out, names = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
W = 640
rows = []
for n in names:
    pa, pb = os.path.join(a, n + '.png'), os.path.join(b, n + '.png')
    if not (os.path.exists(pa) and os.path.exists(pb)): continue
    ia, ib = Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')
    h = int(ia.height * W / ia.width)
    rows.append((n, ia.resize((W, h)), ib.resize((W, int(ib.height * W / ib.width)))))
H = sum(max(r[1].height, r[2].height) + 24 for r in rows) + 28
im = Image.new('RGB', (W * 2 + 12, H), (24, 24, 24)); d = ImageDraw.Draw(im)
try: F = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 16)   # кириллица: шрифт PIL по умолчанию её не знает
except OSError: F = None
d.text((8, 6), 'ДО: ' + os.path.basename(a.rstrip('/')), fill=(255, 255, 255), font=F); d.text((W + 20, 6), 'ПОСЛЕ: ' + os.path.basename(b.rstrip('/')), fill=(255, 255, 255), font=F)
y = 28
for n, ia, ib in rows:
    d.text((8, y + 4), n, fill=(255, 220, 120), font=F); y += 24
    im.paste(ia, (0, y)); im.paste(ib, (W + 12, y)); y += max(ia.height, ib.height)
im.save(out); print(out, len(rows))
