#!/usr/bin/env python3
"""Два пиксельных шрифта Patrick H. Lauke (CC BY 3.0, лицензии в assets/fonts/pixel/) в панели типографики (11.10, слово Роба: «примерить два шрифта»).

Только панель: ui_export и игра эти грани не знают (экспорт и титры с автором делает Бонус позже). Шрифты рисуются по сетке пикселей без сглаживания:
сетка обоих файлов 8 клеток на em (проверено: наибольший общий делитель длин всех пробегов при размере 128 равен 16), значит родной размер 8 px = 1 клетка шрифта = 1 px экрана,
кратные размеры 16, 24, 32 (метки грани @1, *2, *3, *4) — целое повторение пикселей, без фильтра. Метрики берутся из файла (ширина знака, левый отступ по границе рисунка);
строка 10 px и база 8, как у pix8 и msx_thin (viewer/ui_layout.h), знаков, которых нет в шрифте (кириллица), нет в таблице: панель рисует «?» как у граней диска.

    python tools/typo_panel_pixfonts.py [--page build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html] [--out ...]   встроить шрифты и правку JS в готовую страницу
    python tools/typo_panel_pixfonts.py --template                                                  правка JS в шаблоне typo_panel_page.html (для следующей пересборки)
"""
import argparse
import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / 'assets/fonts/pixel'
FONTS = {
    'bart_16bit': dict(file='bart-vs-the-space-mutants-16bit.otf', label='Bart vs the Space Mutants · 16-bit (Lauke, CC BY 3.0)'),
    'simpsons_pix': dict(file='the-simpsons.otf', label='The Simpsons · пиксельный (Lauke, CC BY 3.0)'),
}
NATIVE = 8          # px на em = клеток сетки шрифта
LINE = 10           # высота строки родного размера (как pix8_8 и msx_thin)
BASE = 8            # строка базовой линии внутри ячейки


def build_font(path):
    """-> запись T.fonts для панели: атлас 160x160 (ячейка 10x10 на код, как у msx_thin), глифы [код, x, y, w, h, adv, left]"""
    font = ImageFont.truetype(str(path), NATIVE)
    ref = _mask(font, '')                            # образ «нет знака» (рамка-заглушка)
    atlas = np.zeros((160, 160), np.uint8)
    glyphs = []
    for code in range(32, 256):
        ch = chr(code)
        bm = _mask(font, ch)
        if code != 32 and (bm is None or _same(bm, ref)):
            continue                                      # нет в шрифте: не кладём, панель возьмёт «?»
        adv = int(round(font.getlength(ch)))
        if bm is None:
            glyphs.append([code, (code % 16) * 10, (code // 16) * 10, 0, LINE, adv, 0])
            continue
        x0, y0 = (code % 16) * 10, (code // 16) * 10
        rows, left = bm
        w = rows.shape[1]
        atlas[y0:y0 + LINE, x0:x0 + min(w, 10)] = rows[:LINE, :10] * 255
        glyphs.append([code, x0, y0, min(w, 10), LINE, adv, left])
    return dict(w=160, h=160, height=LINE, baseline=BASE, gscale=1.0, pixel=1,
                alpha=base64.b64encode(atlas.reshape(-1).tobytes()).decode('ascii'), glyphs=glyphs)


def _same(a, b):
    return a is not None and b is not None and a[0].shape == b[0].shape and bool((a[0] == b[0]).all())


def _mask(font, ch):
    """знак на родном размере без сглаживания -> (строки ячейки LINE x ширина рисунка, левый отступ) или None (пусто)"""
    im = Image.new('L', (24, 24), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    ox, oy = 6, 14                                        # начало пера: x 6, база на строке 14
    d.text((ox, oy), ch, font=font, fill=255, anchor='ls')
    a = np.asarray(im) > 0
    ys, xs = np.where(a)
    if not len(xs):
        return None
    x0, x1 = xs.min(), xs.max() + 1
    cell = np.zeros((LINE, x1 - x0), np.uint8)
    for y in range(24):
        cy = y - oy + BASE
        if 0 <= cy < LINE:
            cell[cy] |= a[y, x0:x1].astype(np.uint8)
    return cell, int(x0 - ox)


# ---------------------------------------------------------------- правка JS страницы (шаблон и готовая страница)
EDITS = [
    # 1. список и подписи
    ("var FONT_OPTS = ['boulder_16', 'boulder_24', 'Tt2001m__14', 'swz721n_10', 'swz721mi_12', 'msx_thin'];",
     "var FONT_OPTS = ['boulder_16', 'boulder_24', 'Tt2001m__14', 'swz721n_10', 'swz721mi_12', 'msx_thin', 'bart_16bit', 'simpsons_pix'];\n"
     "var NATIVE_FACE = {msx_thin: 1, bart_16bit: 1, simpsons_pix: 1};   // родной размер 1:1 при выборе (@1), кратные только целые"),
    ("msx_thin: 'Дисклеймер при запуске · тонкий 8×8 (msx)'};",
     "msx_thin: 'Дисклеймер при запуске · тонкий 8×8 (msx)',\n"
     "                bart_16bit: 'Bart vs the Space Mutants · 16-bit (Lauke, CC BY 3.0)', simpsons_pix: 'The Simpsons · пиксельный (Lauke, CC BY 3.0)'};"),
    # 2. выбор шрифта: родной размер для всех «родных» граней, не только msx_thin
    ("else if (!s.fs || s.fs === d.fs) s.fs = +(T.fonts[v].gscale * 1.0).toFixed(4); } build(); onChange(); },",
     "else if (!s.fs || s.fs === d.fs) s.fs = +(T.fonts[v].gscale * 1.0).toFixed(4); } build(); onChange(); },"),
    ("if (v === 'msx_thin') { s.fs = 1; s.ftrk = 0; s.flead = 0; } else if (!s.fs",
     "if (NATIVE_FACE[v]) { s.fs = 1; s.ftrk = 0; s.flead = 0; } else if (!s.fs"),
    ("s.base = v; s.font = v; if (v === 'msx_thin') { s.fs = 1; s.ftrk = 0; s.flead = 0; } } build(); onChange(); },",
     "s.base = v; s.font = v; if (NATIVE_FACE[v]) { s.fs = 1; s.ftrk = 0; s.flead = 0; } } build(); onChange(); },"),
    # 3. растр: целое повторение пикселей у пиксельных шрифтов
    ("var F = s.F, P = 2, fs = p.at ? 1.0 : F.gscale * (p.mul ? parseFloat(p.mul) : 1.0);",
     "var F = s.F, P = 2, fs = p.at ? 1.0 : F.gscale * (p.mul ? parseFloat(p.mul) : 1.0);\n"
     "  var PX = !!F.pixel; if (PX) fs = Math.max(1, Math.round(fs));     // пиксельный шрифт: только целые кратные"),
    ("      if (fs === 1.0) {\n        bm = new Uint8Array(cw * chh);",
     "      if (PX && fs > 1) {                    // целое повторение пикселей без фильтра\n"
     "        var K = fs, ow = cw * K, oh = chh * K; bm = new Uint8Array(ow * oh);\n"
     "        for (var yy = 0; yy < oh; yy++) for (var xx = 0; xx < ow; xx++) bm[yy * ow + xx] = npRound(f32(cell[Math.floor(yy / K) * cw + Math.floor(xx / K)] * 15));\n"
     "        bw = ow; bh = oh; left = g.left * K;\n"
     "      } else if (fs === 1.0) {\n        bm = new Uint8Array(cw * chh);"),
    # 4. имя грани: у пиксельного шрифта кратное всегда целое
    ("var core = Math.abs(s.fs - 1) < 5e-5 ? base + '@1' : base + '*' + fmtNum(s.fs / T.fonts[base].gscale);",
     "var PXF = T.fonts[base] && T.fonts[base].pixel, PXK = PXF ? Math.max(1, Math.round(s.fs / T.fonts[base].gscale)) : 0;\n"
     "  var core = PXF ? (PXK === 1 ? base + '@1' : base + '*' + PXK) : (Math.abs(s.fs - 1) < 5e-5 ? base + '@1' : base + '*' + fmtNum(s.fs / T.fonts[base].gscale));"),
    # 5. правило выравнивания подписей кнопок (ui_typo._align, HINT_ALIGN, коммит 3f9c09e2): после _corner, до сдвига dx/dy
    ("        var icons = corner(its, stat, o.trk | 0), ik = o.icon_k !== undefined ? o.icon_k : 1;\n",
     "        var icons = corner(its, stat, o.trk | 0), ik = o.icon_k !== undefined ? o.icon_k : 1;\n        if (g.align) alignHints(its, stat, g.align, o.trk | 0);   // ui_typo._align (правило Роба 11.10: Accept не гуляет между экранами)\n"),
    ("function corner(its, stat, trk) {",
     "function alignHints(its, stat, al, trk) {     // ui_typo._align: right/bottom — правый край подписи и нижняя строка от краёв экрана; x/y — левый верх нижней строки; значок едет с подписью\n"
     "  var ys = []; its.forEach(function (t) { if (ys.indexOf(t.dst[1]) < 0) ys.push(t.dst[1]); }); ys.sort(function (a, b) { return b - a; });\n"
     "  var pitch = al.pitch !== undefined ? al.pitch | 0 : 20;\n"
     "  its.forEach(function (t) {\n"
     "    var x = t.dst[0], y = t.dst[1], h = t.dst[3], i = ys.indexOf(y), f = t.pix8 ? pix8Font(trk, 0) : getFace(t.font), nw = 0, nx, ny;\n"
     "    t.strings.forEach(function (s) { if (s) nw = Math.max(nw, lineW(f, codes(s), 0, s.length)); });\n"
     "    if (al.right !== undefined) { nx = 480 - (al.right | 0) - nw; ny = 272 - (al.bottom | 0) - h - i * pitch; } else { nx = al.x | 0; ny = (al.y | 0) - i * pitch; }\n"
     "    stat.forEach(function (q) { if (q.page === t.page && T.hint_pages.indexOf(q.page) >= 0) q.cur = [q.cur[0] + nx - x, q.cur[1] + ny - y].concat(q.cur.slice(2)); });\n"
     "    t.dst = [nx, ny, nw, h];\n"
     "  });\n"
     "}\n"
     "function corner(its, stat, trk) {"),
]


def patch_js(text):
    out = text
    for a, b in EDITS:
        if a == b:
            continue
        if b in out:
            continue                                      # уже применено
        if a not in out:
            raise SystemExit('нет якоря правки: ' + a[:90])
        out = out.replace(a, b, 1)
    return out


def inject_fonts(page):
    key = 'window.TYPO = '
    i = page.index(key) + len(key)
    data, end = json.JSONDecoder().raw_decode(page[i:])
    for name in FONTS:
        data['fonts'][name] = build_font(FONT_DIR / FONTS[name]['file'])
    return page[:i] + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + page[i + end:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default=str(ROOT / 'build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html'))
    ap.add_argument('--out')
    ap.add_argument('--template', action='store_true')
    a = ap.parse_args()
    if a.template:
        p = Path(__file__).resolve().parent / 'typo_panel_page.html'
        p.write_text(patch_js(p.read_text()))
        print('шаблон:', p)
        return 0
    src = Path(a.page)
    page = src.read_text()
    page = patch_js(inject_fonts(page))
    out = Path(a.out) if a.out else src
    out.write_text(page)
    print('страница:', out, len(page))
    return 0


if __name__ == '__main__':
    sys.exit(main())
