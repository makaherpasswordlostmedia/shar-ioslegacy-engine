#!/usr/bin/env python3
# №970: листы «до / после» крупно: shots.py ACC_DIR OUT_DIR. Вырезка — вокруг блика (разница с none), увеличение ×4 (серия ×2). Сверху прежнее (flag glint970old 1), снизу новое.
import sys, os
from PIL import Image, ImageDraw
import numpy as np
A, S = sys.argv[1], sys.argv[2]; os.makedirs(S, exist_ok=True)
def img(d, n): return Image.open(os.path.join(A, 'out_' + d, n + '.png')).convert('RGB')
def box(a, n, none_d='none', pad=14, minw=110, minh=80):
    none = np.asarray(img(none_d, n)).astype(int); m = None
    for d in a:
        g = np.abs(np.asarray(img(d, n)).astype(int) - none).sum(axis=2); g[:60] = 0; m = (g > 12) if m is None else (m | (g > 12))
    ys, xs = np.nonzero(m)
    if not len(xs): return (100, 80, 380, 240)
    x0, x1, y0, y1 = xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; w = max(x1 - x0, minw); h = max(y1 - y0, minh)
    return (int(max(0, cx - w / 2)), int(max(60, cy - h / 2)), int(min(480, cx + w / 2)), int(min(272, cy + h / 2)))
def sheet(obj, names, name, k=4, per_row=None):
    sfx = obj
    rows = []
    for tag, d in (('OLD TEST66', obj + '_old'), ('NEW 970', obj + '_new')):
        ims = []
        for n in names:
            b = box([obj + '_old', obj + '_new'], n, obj + '_none'); im = img(d, n).crop(b); im = im.resize((im.width * k, im.height * k), Image.LANCZOS); ims.append(im)
        rows.append((tag, ims))
    w = max(i.width for _, ims in rows for i in ims); h = max(i.height for _, ims in rows for i in ims)
    per = per_row or len(names); nr = (len(names) + per - 1) // per
    out = Image.new('RGB', (w * per, (h + 18) * nr * 2), (20, 20, 20)); dr = ImageDraw.Draw(out)
    for r, (tag, ims) in enumerate(rows):
        for i, im in enumerate(ims):
            y = ((i // per) * 2 + r) * (h + 18); x = (i % per) * w
            out.paste(im, (x, y + 18)); dr.text((x + 4, y + 3), '%s  %s' % (tag, names[i]), fill=(255, 255, 255))
    out.save(os.path.join(S, name)); print(name, out.size)
if not (len(sys.argv) > 3 and sys.argv[3] == '976'):
    sheet('w', ['k7'], 'ключ_до_после.png', 4)
    sheet('w', ['p%02d' % i for i in range(16)], 'ключ_серия_пульсации.png', 2, 4)
    sheet('p', ['ph0', 'ph1', 'ph2', 'ph3'], 'будка_до_после.png', 3, 2)
    sheet('c', ['c_l1_a', 'c_l1_c', 'c_l2_b', 'c_l5_d'], 'монета_до_после.png', 4, 2)
    sheet('l', ['l_a', 'l_c', 'l_e'], 'огни_до_после.png', 4)

if len(sys.argv) > 3 and sys.argv[3] == '976':   # №976: кольцо цели (вырезка вручную) и серия входа (вырезка по звёздам)
    sheet('sphere', ['e%02d' % i for i in range(10)], 'цель_звёзды_серия.png', 2, 2)
    rows = []
    for tag, d in (('OLD TEST66', 'sphere_old'), ('NEW 976', 'sphere_new')):
        im = img(d, 'ring_a').crop((40, 95, 420, 245)); rows.append((tag, im.resize((im.width * 3, im.height * 3), Image.LANCZOS)))
    out = Image.new('RGB', (rows[0][1].width, (rows[0][1].height + 18) * 2), (20, 20, 20)); dr = ImageDraw.Draw(out)
    for r, (tag, im) in enumerate(rows): out.paste(im, (0, r * (im.height + 18) + 18)); dr.text((4, r * (im.height + 18) + 3), tag, fill=(255, 255, 255))
    out.save(os.path.join(S, 'цель_кольцо_до_после.png')); print('цель_кольцо_до_после.png')
