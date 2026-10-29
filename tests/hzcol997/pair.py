import sys
from PIL import Image
# pair.py DIR_OLD DIR_NEW PREF OUT [indices]  — лист «TEST70 / стало»: строка = направление, слева прежнее, справа новое
a, b, pref, out = sys.argv[1:5]; idx = [int(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 else range(6)
w, h = 480, 272; rows = []
for i in idx:
    im = Image.new('RGB', (2 * w + 6, h), (30, 30, 30))
    im.paste(Image.open(f'{a}/{pref}_d{i}.png').convert('RGB'), (0, 0)); im.paste(Image.open(f'{b}/{pref}_d{i}.png').convert('RGB'), (w + 6, 0)); rows.append(im)
s = Image.new('RGB', (2 * w + 6, len(rows) * (h + 4)), (30, 30, 30))
for k, r in enumerate(rows): s.paste(r, (0, k * (h + 4)))
s.save(out)
