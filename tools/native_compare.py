#!/usr/bin/env python3
"""№566: сравнение растра родных шрифтов диска «было / стало» (дробный масштаб до и после чистки, tools/ui_export.py FontCache._native_hinted).
Строки — из игры; ×1 и ×3 (целое повторение пикселей). python tools/native_compare.py [--out FILE.png]"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_export as U

ROWS = [('boulder_24*1.3235', 'PAUSE MENU'), ('boulder_24*1.0084', 'THE COLA CAPER'), ('boulder_16*1.8', 'CONTINUE   RESET CAR'), ('boulder_24*0.9454', 'YES   NO'),
        ('swz721mi_12*1.8667', '1/3 LAPS  4th'), ('Tt2001m__14*1.06', 'Disable Tutorials'), ('swz721n_10*1.5', 'ACCELERATION')]


def draw(fc, face, text, col=(255, 230, 40)):
    f = fc.get(face); w = sum(f['glyphs'].get(ord(c), f['glyphs'][63])['adv'] for c in text) + 6
    im = np.zeros((f['lh'] + 4, w, 4), np.uint8); pen = 2
    for c in text:
        g = f['glyphs'].get(ord(c)) or f['glyphs'][63]
        if g['bm'] is not None:
            bm = g['bm']; x0 = pen + g['left']
            for y in range(bm.shape[0]):
                for x in range(bm.shape[1]):
                    a = float(bm[y, x])
                    if a > 0 and 0 <= x0 + x < w and 2 + y < im.shape[0]: im[2 + y, x0 + x] = (*col, int(a * 255))
        pen += g['adv']
    return Image.fromarray(im, 'RGBA')


def sheet(out):
    old = U.FontCache('psp'); U.NATIVE_PIX_ON = False; olds = [(f, t, draw(U.FontCache('psp'), f, t)) for f, t in ROWS]
    U.NATIVE_PIX_ON = True; news = [(f, t, draw(U.FontCache('psp'), f, t)) for f, t in ROWS]
    H = sum(max(o[2].height, n[2].height) * 3 + 14 for o, n in zip(olds, news)) + 10
    W = max(o[2].width for o in olds + news) * 3 * 2 + 40
    img = Image.new('RGBA', (W, H), (52, 70, 120, 255)); y = 6
    for (f, t, o), (_, _, n) in zip(olds, news):
        h = max(o.height, n.height) * 3
        img.alpha_composite(o.resize((o.width * 3, o.height * 3), Image.NEAREST), (6, y))
        img.alpha_composite(n.resize((n.width * 3, n.height * 3), Image.NEAREST), (W // 2 + 6, y)); y += h + 14
    img.convert('RGB').save(out)
    return out


def page(out_dir):
    """native_compare.html рядом со страницей панели: каждая родная грань (по умолчанию из игры и выбранные Робом в ui_typo.json): было / стало, ×1 и ×3, строкой из игры"""
    import base64, io, json
    rows = list(ROWS)
    try:
        for gid, v in json.load(open(U.ROOT / 'build/ui_typo.json')).get('groups', {}).items():
            f = v.get('face') or (v.get('font') if v.get('font') not in (None, 'pix8') else None)
            if f and f.partition('*')[0].partition('@')[0].partition('+')[0].partition('^')[0] in ('boulder_16', 'boulder_24', 'Tt2001m__14', 'swz721n_10', 'swz721mi_12') \
                    and '@' not in f and '*' in f and all(f != r[0] for r in rows):
                rows.append((f.partition('+')[0].partition('^')[0], 'THE COLA CAPER  Continue  4th'))
    except Exception:
        pass
    def b64(im):
        b = io.BytesIO(); im.save(b, 'PNG'); return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
    U.NATIVE_PIX_ON = False; olds = {f: draw(U.FontCache('psp'), f, t) for f, t in rows}
    U.NATIVE_PIX_ON = True; news = {f: draw(U.FontCache('psp'), f, t) for f, t in rows}
    cells = []
    for f, t in rows:
        row = ['<h3>%s <small>%s</small></h3><div class="r">' % (f, t)]
        for lab, im in (('было', olds[f]), ('стало', news[f])):
            for k in (1, 3):
                row.append('<figure><img style="image-rendering:pixelated;width:%dpx" src="%s"><figcaption>%s ×%d</figcaption></figure>' % (im.width * k, b64(im), lab, k))
        cells.append(''.join(row) + '</div>')
    html = ('<!doctype html><meta charset="utf-8"><title>Сравнение граней</title><style>body{font:14px system-ui;background:#2a3a66;color:#eee;margin:24px}'
            'h3{margin:18px 0 6px}small{opacity:.6;font-weight:400}.r{display:flex;gap:28px;align-items:flex-end;flex-wrap:wrap;background:#34467a;padding:12px;border-radius:12px}'
            'figure{margin:0}figcaption{opacity:.7;font-size:12px;margin-top:4px}</style><h2>Родные шрифты диска: было (дробный масштаб, серые края) и стало (привязка к сетке, чистый край)</h2>'
            + ''.join(cells))
    (Path(out_dir) / 'native_compare.html').write_text(html)
    return Path(out_dir) / 'native_compare.html'


if __name__ == '__main__':
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'native_compare.png'
    print(sheet(out))
    if '--page' in sys.argv: print(page(sys.argv[sys.argv.index('--page') + 1]))
