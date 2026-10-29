#!/usr/bin/env python3
"""Гейт правок Роба 136 и 163 «шрифт меню — пиксель-перфект под разрешение PSP; межбуквенный шире» (хост, Мак, CPU).

  python3 tests/ui/menu_font_check.py [--dir build]

Читает пакеты так, как их читает viewer/ui.c: ui.shr (главное меню, пауза, пауза миссии и все экраны с подписями кнопок),
menu.shr (OPTIONS и SOUND главного меню), pmenu.shr (OPTIONS и SOUND паузы), pextra.shr (подписи VIEW CARDS, MISSION SELECT);
раскладки — build/ui/layout.json, layout_menu.json, layout_pmenu.json, layout_pextra.json. Проверяемые строки:
  · строка главного меню (MainMenu0..5), пункты паузы и паузы миссии, OPTIONS паузы и главного меню, подписи ползунков SOUND;
  · подписи кнопок (Accept, Back, Continue, Quit — страницы Accept/Back/Accept3/Continue.pag) всех экранов этих пакетов.
Для каждой буквы их строк:
  · масштаб грани целый: высота строки = высоте грани диска (или целое кратное), иначе — дробный пересэмпл (правка 136);
  · битмап атласа попиксельно = ячейке шрифта диска (альфа диска, 16 уровней), без промежуточной альфы пересэмпла;
  · отступ = отступу диска + трекинг // 2, адванс = адвансу диска + трекинг: трекинг один на всю грань, целый и не меньше
    TRACK_MIN px (правка 163: «межбуквенный был шире — очень плотно, сливается в кашу»);
  · подписи кнопок всех экранов — одной гранью (правка 163: «ACCEPT толстое и тонкое» — не смесь boulder и Tt2001m);
  · строка главного меню со стрелками целиком в кадре 480x272.
Красные (tests/menu_font/run.sh): UI_MENU_SOFT=1 — дробная грань boulder_24*1.35 (до правки 136); UI_DENSE=1 — раскладка до
правки 163 (грани без трекинга, пункты паузы дробные, подписи кнопок вперемешку)."""
import argparse, json, pathlib, struct, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U

TRACK_MIN = 0        # правка 201 (Роб 03.10, после 163 и 190): «меньше меж букв» — шаг диска 1:1 без разрядки, как у оригинала
                     # (близнец 01.10: пункты паузы и NEW GAME без разрядки). «Каша» правки 163 была от дробного пересэмпла, не от шага
MAIN_TRACK_MIN = 0   # правка 190: NEW GAME… без разрядки (1:1)
FREC = 16 + 8 * 256
ap = argparse.ArgumentParser()
ap.add_argument('--dir', default=str(ROOT / 'build'))
a = ap.parse_args()
D = pathlib.Path(a.dir)
# пакет: (файл, раскладка, экраны со строками меню)
PACKS = [('ui.shr', 'layout.json', ('main', 'pause', 'pausemsn')),
         ('menu.shr', 'layout_menu.json', ('options', 'sound')),
         ('pmenu.shr', 'layout_pmenu.json', ('pauseoptions', 'pausesound')),
         ('pextra.shr', 'layout_pextra.json', ())]
disk = U.all_fonts()


class Pak:
    def __init__(self, path, layout):
        self.b = pathlib.Path(path).read_bytes()
        hdr = struct.unpack_from('<4s19I', self.b, 0)
        self.ntex, self.otex, self.nitem, self.oitem, self.nscreen, self.oscreen, self.nfont, self.ofont, self.nstr, self.ostr = hdr[2:12]
        self.screens = json.loads(pathlib.Path(layout).read_text())['screens']
        self.atlas = {}

    def string(self, i):
        o = struct.unpack_from('<I', self.b, self.ostr + 4 * i)[0]; e = self.b.index(b'\0', o); return self.b[o:e].decode('latin-1')

    def tex_alpha(self, ti):
        if ti not in self.atlas:
            psm, flags, w, h, op, oc, nc, bw, rows, _ = struct.unpack_from('<4H6I', self.b, self.otex + ti * 32)
            rb = bw if psm == 5 else bw // 2
            raw = np.frombuffer(self.b, np.uint8, count=rb * rows, offset=op)
            raw = raw.reshape(rows // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rows, rb) if flags & 1 else raw.reshape(rows, rb)
            idx = np.empty((rows, rb * 2), np.uint8); idx[:, 0::2] = raw & 15; idx[:, 1::2] = raw >> 4
            pal = np.frombuffer(self.b, np.uint8, count=nc * 4, offset=oc).reshape(nc, 4)
            self.atlas[ti] = pal[idx][..., 3].astype(np.int32)
        return self.atlas[ti]

    def items(self, sc):
        names = list(self.screens)
        first, count = struct.unpack_from('<4I', self.b, self.oscreen + 16 * names.index(sc))[:2]
        lay = self.screens[sc]
        if len(lay) != count:
            sys.exit('menu_font: %s не соответствует пакету' % sc)
        for k, t in enumerate(lay):
            yield t, self.b[self.oitem + (first + k) * 64: self.oitem + (first + k + 1) * 64]


def check_face(pk, r, track_min=None):
    """грань элемента r (запись 64 Б): (имя, строка lh, заглавная, трекинг, [нарушения])"""
    fi = r[26]; sfirst, scount = struct.unpack_from('<2H', r, 28)
    ftex, lh, base, _, fname, _ = struct.unpack_from('<4H2I', pk.b, pk.ofont + fi * FREC)
    face = pk.string(fname); f = disk[U.face_base(face)]
    da = np.asarray(f['image'].convert('RGBA'))[..., 3].astype(np.float64) / 255
    k_int = lh / f['height']
    bad, tracks = [], set()
    if abs(k_int - round(k_int)) > 1e-6 or round(k_int) < 1:
        return face, lh, 0, None, ['строка %d px = %.3f x высоты грани диска %.0f — масштаб не целый' % (lh, k_int, f['height'])]
    kk = int(round(k_int)); A = pk.tex_alpha(ftex)
    for sv in (pk.string(sfirst + j) for j in range(scount)):
        for ch in sv:
            gx, gy, gw, gl, gadv, gfl = struct.unpack_from('<HHBbBB', pk.b, pk.ofont + fi * FREC + 16 + 8 * ord(ch))
            dg = f['glyphs'].get(ord(ch))
            if dg is None:
                continue
            t = gadv - int(dg['adv']) * kk; tracks.add(t)
            if gl != int(dg['left']) * kk + t // 2:
                bad.append('%r: отступ %d != диск %d + трекинг//2 (%d)' % (ch, gl, int(dg['left']) * kk, t // 2)); continue
            if not (gfl & 1):
                continue
            cw, ch_ = int(dg['w']), int(dg['h']); x0d, y0d = int(dg['x']), int(dg['y'])
            cell = np.kron(np.round(da[y0d:y0d + ch_, x0d:x0d + cw] * 15).astype(np.int32), np.ones((kk, kk), np.int32))
            got = A[gy:gy + lh, gx:gx + gw] // 17
            want = np.zeros((lh, cw * kk), np.int32); want[:min(lh, cell.shape[0]), :] = cell[:lh]
            if gw != cw * kk or got.shape != want.shape:
                bad.append('%r: ячейка %dx%d != диск %dx%d' % (ch, gw, lh, cw * kk, lh)); continue
            if (got != want).any():
                bad.append('%r: %d пикс. не как на диске' % (ch, (got != want).sum()))
    track = None
    if len(tracks) > 1:
        bad.append('трекинг разный у разных букв %s' % sorted(tracks))
    elif tracks:
        track = tracks.pop()
        tm = TRACK_MIN if track_min is None else track_min
        if track < tm:
            bad.append('трекинг %d < %d px — буквы впритык (правка 163)' % (track, tm))
    g = f['glyphs'][ord('N')]
    cap = int(np.ptp(np.where(da[int(g['y']):int(g['y'] + g['h']), int(g['x']):int(g['x'] + g['w'])].max(1) >= .5)[0]) + 1) * kk
    return face, lh, cap, track, bad


fails, report, hint_faces = [], {}, {}
row = dict(x0=480, x1=0, y0=272, y1=0)
for fname, lname, menu_screens in PACKS:
    pk = Pak(D / fname, D / 'ui' / lname)
    for sc in pk.screens:
        for t, r in pk.items(sc):
            x, y, w, h = struct.unpack_from('<4h', r, 8)
            if sc == 'main' and t['name'].startswith('MainMenu'):
                row['x0'] = min(row['x0'], x); row['x1'] = max(row['x1'], x + w); row['y0'] = min(row['y0'], y); row['y1'] = max(row['y1'], y + h)
            if t['type'] != U.T_TEXT:
                continue
            hint = t['page'] in U.HINT_PAGES
            item = sc in menu_screens and ((sc == 'main' and t['name'].startswith('MainMenu')) or (sc != 'main' and r[7] & 8))
            if not (hint or item):
                continue
            # правка 190 (01.10 22:2x, после 163): строка главного меню — 1:1 без разрядки, как у оригинала (близнец v15_boot2)
            face, lh, cap, track, bad = check_face(pk, r, MAIN_TRACK_MIN if (item and sc == 'main') else None)
            fam = 'подписи кнопок' if hint else ('строка главного меню' if sc == 'main' else 'пункты %s' % sc)
            report.setdefault(fam, set()).add('%s, строка %d px%s%s' % (face, lh, ', заглавная %d px' % cap if cap else '',
                                                                       ', трекинг +%d' % track if track is not None else ''))
            if hint:
                hint_faces.setdefault(face, []).append('%s/%s' % (sc, t['name']))
            if bad:
                fails.append('%s %s/%s (%s): %s' % (fname, sc, t['name'], face, bad[0]) + (' (и ещё %d)' % (len(set(bad)) - 1) if len(set(bad)) > 1 else ''))
if len(hint_faces) > 1:
    fails.append('подписи кнопок разными гранями: ' + '; '.join('%s — %s' % (f, ', '.join(v[:3]) + (' …' if len(v) > 3 else ''))
                                                              for f, v in hint_faces.items()))
if row['x0'] < 0 or row['x1'] > 480 or row['y0'] < 0 or row['y1'] > 272:
    fails.append('строка меню со стрелками вне кадра: %s' % row)
for fam, ls in report.items():
    print('%s: %s' % (fam, ' | '.join(sorted(ls))))
print('строка меню со стрелками: x %d..%d, y %d..%d (кадр 480x272)' % (row['x0'], row['x1'], row['y0'], row['y1']))
if fails:
    print('КРАСНЫЙ: ' + ' | '.join(dict.fromkeys(fails[:12])) + (' … всего %d' % len(fails) if len(fails) > 12 else '')); sys.exit(1)
print('ЗЕЛЁНЫЙ: буквы меню, паузы и подписей кнопок — ячейки шрифта диска 1:1 (целый масштаб), трекинг >= %d px, подписи одной гранью'
      % TRACK_MIN)
