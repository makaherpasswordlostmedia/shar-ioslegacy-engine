#!/usr/bin/env python3
"""Листы для Роба (правки 129 и 144), только чтение level.shr — до и после:
  sign   вывески: уровень 0 и вид издали (мип 1, 2) — было (256, T8) / стало (128 и T4, где прошло порог)
  t4     текстуры, ушедшие в T4: мипы 1..3 было / стало (вдали — 16 цветов уровня 0)
  tone   насыщенность: прежняя кривая 1.28 (жёсткий кламп) / 1.36 (по умолчанию) / 1.60 / 1.00 (мягкий потолок)
    TEX_NAMES=names.json python tools/tex_sheet.py OLD.shr NEW.shr OUTDIR
"""
import sys, json, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tex_gate as G  # noqa: E402


def level(b, rec, li):
    p, w, h, nl, t4, pre, lv = rec
    if li >= len(lv): li = len(lv) - 1
    q, lw, lh, rb, rows = lv[li]
    a = np.frombuffer(b, np.uint8, rb * rows, q)
    a = a.reshape(rows // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rows, rb) if pre else a.reshape(rows, rb)
    if t4: a = np.stack([a & 15, a >> 4], -1).reshape(rows, 2 * rb)
    pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4)
    return pal[a[:lh, :lw]], pal


def tone(rgba, sat, soft):
    c = rgba.astype(np.float32)
    v = 255 * (c[..., :3] / 255) ** 1.10; v = (v - 128) * 1.12 + 128; q = np.clip(np.floor(v + .5), 0, 255)
    y = (q * [.299, .587, .114]).sum(-1, keepdims=True); d = q - y; k = np.full(y.shape, sat, np.float32)
    if soft:
        with np.errstate(divide='ignore', invalid='ignore'):
            lim = np.where(d > .5, (255 - y) / d, np.where(d < -.5, -y / d, 1e9))
        k = np.maximum(1, np.minimum(k, lim.min(-1, keepdims=True)))
    out = rgba.copy(); out[..., :3] = np.clip(np.floor(y + d * k + .5), 0, 255).astype(np.uint8)
    return out


def tile(rgba, size, bg=(40, 40, 40)):
    im = Image.fromarray(np.ascontiguousarray(rgba), 'RGBA')
    sc = min(size[0] / im.width, size[1] / im.height)
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.NEAREST)
    base = Image.new('RGB', size, bg); base.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2), im)
    return base


def sheet(rows, cols, cell, title, path):
    W = 180 + len(cols) * (cell[0] + 8); H = 40 + len(rows) * (cell[1] + 8)
    img = Image.new('RGB', (W, H), (20, 20, 20)); d = ImageDraw.Draw(img)
    try: f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)   # кириллица (шрифт PIL по умолчанию — без неё)
    except OSError: f = None
    d.text((8, 6), title, fill=(230, 230, 230), font=f)
    for j, c in enumerate(cols): d.text((180 + j * (cell[0] + 8), 22), c, fill=(200, 200, 120), font=f)
    for i, (name, tiles) in enumerate(rows):
        y = 40 + i * (cell[1] + 8); d.text((8, y + cell[1] // 2), name, fill=(220, 220, 220), font=f)
        for j, t in enumerate(tiles): img.paste(t, (180 + j * (cell[0] + 8), y))
    img.save(path); print(path)


def main():
    old, new, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    bo, bn = Path(old).read_bytes(), Path(new).read_bytes()
    ro, _, _, _ = G.walk(bo); rn, _, _, _ = G.walk(bn)
    src = json.loads(Path(new + '.texsrc.json').read_text())['tex']
    names = {}
    nj = Path(os.environ.get('TEX_NAMES', '/nonexistent'))   # json {digest: [[имя.bmp, файл.p3d], …]} — подписи; нет — хеш
    if nj.exists():
        for k, v in json.loads(nj.read_text()).items(): names['textures/%s.png' % k] = v[0][0].replace('.bmp', '')
    nm = lambda i: names.get(src[i]['url'], src[i]['url'][-24:-4]) if src[i] else str(i)
    idx = {s['url']: i for i, s in enumerate(src) if s}
    # 1) вывески
    rows = []
    for u in G.SIGN:
        i = idx.get(u)
        if i is None: continue
        a = [level(bo, ro[i], 0)[0], level(bn, rn[i], 0)[0], level(bo, ro[i], 2)[0], level(bn, rn[i], 1)[0]]
        rows.append(('%s %dx%d->%dx%d%s' % (nm(i), ro[i][1], ro[i][2], rn[i][1], rn[i][2], ' T4' if rn[i][4] else ''), [tile(x, (256, 128)) for x in a]))
    sheet(rows, ['было, вблизи', 'стало, вблизи', 'было, 64 px (вдали)', 'стало, 64 px (вдали)'], (256, 128),
          'Правка 129: вывески 256 -> 128 (как весь город). Вдали один и тот же размер на экране', out / 'вывески_до_после.png')
    # 2) T4: самые «трудные» из прошедших порог (наибольшая разница мипов) + трава/тротуар
    cand = []
    for i, (a, c) in enumerate(zip(ro, rn)):
        if not c[4] or a[1:3] != c[1:3]: continue
        e = np.abs(level(bo, a, 2)[0].astype(int) - level(bn, c, 2)[0].astype(int))[..., :3].mean()
        cand.append((e, i))
    cand.sort(reverse=True)
    pick = [i for _, i in cand[:8]] + [i for _, i in cand[len(cand) // 2:len(cand) // 2 + 2]]
    rows = []
    for i in pick:
        t = []
        for li in (1, 2, 3):
            t += [tile(level(bo, ro[i], li)[0], (128, 128)), tile(level(bn, rn[i], li)[0], (128, 128))]
        rows.append(('%s %dx%d' % (nm(i), rn[i][1], rn[i][2]), t))
    sheet(rows, ['мип1 было', 'мип1 T4', 'мип2 было', 'мип2 T4', 'мип3 было', 'мип3 T4'], (128, 128),
          'Правка 129: 4 бита (16 цветов) — уровень 0 тот же побайтно; вдали мипы в тех же 16 цветах (худшие из прошедших порог)',
          out / 't4_мипы_до_после.png')
    # 3) насыщенность (исходные палитры — из файла, до кривой)
    want = ['lard_lad', 'krust_sign', 'k_burger_logo', 'grassc', 'roof_a', 'sidewlk', 'kwiki_sign', 'tomacco', 'billboard', 'asphalt_norm']
    rows = []
    for w_ in want:
        i = next((k for k in range(len(src)) if nm(k) == w_), None)
        if i is None: continue
        a = level(bn, rn[i], 0)[0]
        t = [tile(tone(a, 1.28, False), (192, 128)), tile(tone(a, 1.36, True), (192, 128)), tile(tone(a, 1.60, True), (192, 128)),
             tile(tone(a, 1.00, True), (192, 128))]
        rows.append((w_, t))
    sheet(rows, ['было 1.28', 'стало 1.36 (по умолч.)', '1.60 (макс.)', '1.00 (без)'], (192, 128),
          'Правка 144: насыщенность (Settings паузы -> Colour). Мягкий потолок: яркое не уходит в другой оттенок', out / 'насыщенность.png')


if __name__ == '__main__':
    main()
