#!/usr/bin/env python3
"""Гейт правок Роба 152/153 «надписи титульного, загрузки и демо — на пункт крупнее, ровно по пиксельной сетке PSP» (хост, Мак, CPU).

  python3 tests/ui/boot_font_check.py --pack boot --screens bootload,splash,demo
  python3 tests/ui/boot_font_check.py --pack load --screens loading,loadingfe

Читает build/<pack>.shr (как его читает viewer/ui.c) и build/ui/layout_<pack>.json: все тексты экранов; их грани (таблица
шрифтов), глифы из T4-атласа «fonts». Для каждой буквы их строк (как tests/ui/menu_font_check.py, правка 136):
  · грань целого масштаба: высота строки lh = высоте грани диска (или целое кратное), иначе — дробный масштаб;
  · битмап атласа попиксельно = ячейке шрифта диска (альфа диска), без промежуточной альфы пересэмплирования;
  · адванс и отступ = диску (целые), ширина ячейки = ширине на диске;
  · строка не мельче прежней (заглавная > 7 px — boulder_16 x 272/480) и целиком в кадре 480x272.
Красный: UI_BOOT_SOFT=1 tools/load_export.py — прежняя дробная грань boulder_16 (строка 11 px из 19)."""
import argparse, json, pathlib, struct, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U

ap = argparse.ArgumentParser()
ap.add_argument('--pack', default='boot')
ap.add_argument('--screens', default='bootload,splash,demo')
ap.add_argument('--layout', default=None, help='build/ui/layout.json для ui.shr (правка 158)')
a = ap.parse_args()
b = (ROOT / 'build' / f'{a.pack}.shr').read_bytes()
hdr = struct.unpack_from('<4s19I', b, 0)
ntex, otex, nitem, oitem, nscreen, oscreen, nfont, ofont, nstr, ostr = hdr[2:12]
screens = json.loads((pathlib.Path(a.layout) if a.layout else ROOT / 'build/ui' / f'layout_{a.pack}.json').read_text())['screens']
names = list(screens)


def string(i):
    o = struct.unpack_from('<I', b, ostr + 4 * i)[0]; e = b.index(b'\0', o); return b[o:e].decode('latin-1')


def tex_alpha(ti):
    psm, flags, w, h, op, oc, nc, bw, rows, _ = struct.unpack_from('<4H6I', b, otex + ti * 32)
    rb = bw if psm == 5 else bw // 2
    raw = np.frombuffer(b, np.uint8, count=rb * rows, offset=op)
    raw = raw.reshape(rows // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rows, rb) if flags & 1 else raw.reshape(rows, rb)
    idx = np.empty((rows, rb * 2), np.uint8); idx[:, 0::2] = raw & 15; idx[:, 1::2] = raw >> 4
    pal = np.frombuffer(b, np.uint8, count=nc * 4, offset=oc).reshape(nc, 4)
    return pal[idx][..., 3].astype(np.int32)


FREC = 16 + 8 * 256
disk = U.all_fonts()
fails, report, atlas, ntext = [], [], {}, 0
for sc in a.screens.split(','):
    si = names.index(sc)
    first, count = struct.unpack_from('<4I', b, oscreen + 16 * si)[:2]
    lay = screens[sc]
    if len(lay) != count: sys.exit(f'boot_font: layout_{a.pack}.json не соответствует {a.pack}.shr')
    for k, t in enumerate(lay):
        if t['type'] != U.T_TEXT: continue
        ntext += 1
        r = b[oitem + (first + k) * 64: oitem + (first + k + 1) * 64]
        x, y, w, h = struct.unpack_from('<4h', r, 8)
        fi = r[26]; sfirst, scount = struct.unpack_from('<2H', r, 28)
        ftex, lh, base, _, fname, _ = struct.unpack_from('<4H2I', b, ofont + fi * FREC)
        face = string(fname); f = disk[U.face_base(face)]
        if ftex not in atlas: atlas[ftex] = tex_alpha(ftex)
        A = atlas[ftex]
        da = np.asarray(f['image'].convert('RGBA'))[..., 3].astype(np.float64) / 255
        k_int = lh / f['height']
        bad = []
        if abs(k_int - round(k_int)) > 1e-6 or round(k_int) < 1:
            bad.append(f'строка {lh} px = {k_int:.3f} x высоты грани диска {f["height"]:.0f} — масштаб не целый')
        else:
            kk = int(round(k_int))
            for sv in (string(sfirst + j) for j in range(scount)):
                for ch in sv:
                    gx, gy, gw, gl, gadv, gfl = struct.unpack_from('<HHBbBB', b, ofont + fi * FREC + 16 + 8 * ord(ch))
                    dg = f['glyphs'].get(ord(ch))
                    if dg is None: continue
                    if gadv != int(dg['adv']) * kk or gl != int(dg['left']) * kk: bad.append(f'{ch!r}: адванс/отступ {gadv}/{gl} != диск'); continue
                    if not (gfl & 1): continue
                    cw, ch_ = int(dg['w']), int(dg['h']); x0d, y0d = int(dg['x']), int(dg['y'])
                    cell = np.kron(np.round(da[y0d:y0d + ch_, x0d:x0d + cw] * 15).astype(np.int32), np.ones((kk, kk), np.int32))
                    got = A[gy:gy + lh, gx:gx + gw] // 17
                    want = np.zeros((lh, cw * kk), np.int32); want[:min(lh, cell.shape[0]), :] = cell[:lh]
                    if gw != cw * kk or got.shape != want.shape: bad.append(f'{ch!r}: ячейка {gw}x{lh} != диск {cw * kk}x{lh}'); continue
                    if (got != want).any(): bad.append(f'{ch!r}: {(got != want).sum()} пикс. не как на диске')
        g = f['glyphs'][ord('N')]
        cap = int(np.ptp(np.where(da[int(g['y']):int(g['y'] + g['h']), int(g['x']):int(g['x'] + g['w'])].max(1) >= .5)[0]) + 1) * max(1, int(round(k_int)))
        if not bad and cap <= 7: bad.append(f'заглавная {cap} px — не крупнее прежних 7')
        tw = max(sum(struct.unpack_from('<HHBbBB', b, ofont + fi * FREC + 16 + 8 * ord(c))[4] for c in string(sfirst + j)) for j in range(scount))
        if x < 0 or y < 0 or x + w > 480 or y + max(h, lh) > 272 or tw > max(w, 1):
            bad.append(f'строка вне кадра или шире рамки: x {x} y {y} w {w} h {h}, текст {tw} px')
        report.append(f'{sc}/{t["name"]}: грань {face} строка {lh} px, заглавная {cap} px, рамка {x},{y} {w}x{h}')
        if bad: fails.append(f'{sc}/{t["name"]} ({face}): {bad[0]}' + (f' (и ещё {len(set(bad)) - 1})' if len(set(bad)) > 1 else ''))
for l in report: print(l)
if not ntext: fails.append('ни одного текста — экраны не те')
if fails:
    print('КРАСНЫЙ: ' + ' | '.join(dict.fromkeys(fails))); sys.exit(1)
print(f'ЗЕЛЁНЫЙ: {ntext} надписей {a.pack}.shr — ячейки шрифта диска 1:1 (целый масштаб), крупнее прежнего, в кадре')
