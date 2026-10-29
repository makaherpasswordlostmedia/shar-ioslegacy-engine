#!/usr/bin/env python3
"""Гейт правок Роба 150/151 (01.10): вёрстка паузы и OPTIONS паузы на хосте — по пикселям раскладки, которую рисует движок
(tools/ui_export.py render — зеркало viewer/ui.c), без эмулятора.
    check.py [--shots DIR]   -> первая строка итог по каждому экрану, код 0 = всё зелёное; DIR — снимки x2 для глаза
Экраны: pause (игрок: RESET CAR скрыт, сдвиг строк как viewer/ui.c hideDy), pause_service (все 8 строк), pausemsn, pauseoptions,
pausesound, pausesettings (pmenu.shr, tools/menu_export.py). Меряется отдельными прогонами рисовальщика: буквы строк (без тени),
рамка доски (элементы её страницы), заголовок, счёт монет, подсказки кнопок.
Требования (что Роб назвал словами «больше воздуха между строк, рамку меньше, всё усредни, ничего не налезает»):
  1. шаг строк одинаковый; у меню-колонки (пауза, пауза миссии, OPTIONS) >= PITCH_MIN px (прежний сжатый — 22)
  2. поля доски: сверху = снизу (±1), слева = справа (±1) по самой широкой строке; поле не больше FIELD_MAX x шаг строк
     (рамка по содержимому, а не с запасом), но не меньше просвета между строками (группа не прилипает к рамке)
  3. каждая строка колонки — по центру доски по своим буквам (±1)
  4. ничего не налезает: буквы строк не пересекаются (просвет >= 6), внутри заливки доски (>= 6 px), заголовок над рамкой
     (>= 3 px) и не задевает счёт монет (>= 8 px), подсказки кнопок не на доске, всё в пределах экрана
  5. подписи строк ПРОПИСНЫМИ (пункты паузы, OPTIONS, подписи ползунков SOUND) — заглавные не мельче CAP_MIN px
  6. семейство XSmallBoard (пауза, пауза миссии, OPTIONS) — одна ширина и один верх доски
Правка Роба 163 (01.10 ~14:50: «зачем сделал меню таким узким? рамка не должна постоянно адаптироваться — приятная по ширине;
PAUSE MENU мельче; межбуквенный был шире — сливается в кашу; ACCEPT крупнее»):
  7. ширина доски колонок (пауза, пауза миссии, OPTIONS, SOUND) постоянная — U.PAUSE_BOARD_W (±1), как до правки 150, а не по тексту
  8. буквы подписей ПРОПИСНЫМИ не слипаются: просвет между соседними буквами (по альфе >= 0.5 грани на PSP) >= LETTER_GAP_MIN px
  9. заголовок над доской мельче прежнего (заглавная <= TITLE_CAP_MAX px, было 17), но крупнее заглавной пунктов, и не шире доски
 10. подписи кнопок (✕ Accept, △ Back) крупнее прежнего: заглавная грани >= HINT_CAP_MIN px (была 6 — Tt2001m x 0,69)
Красные (tests/pause_layout/run.sh): PAUSE_OLD=1 — раскладка до правки 150; UI_DENSE=1 — раскладка до правки 163 (рамка 192 по
тексту, буквы впритык, заголовок 17 px, подсказки 6 px)."""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import ui_export as U  # noqa: E402
import menu_export as M  # noqa: E402

PITCH_MIN, FIELD_MAX, SEP_MIN, IN_MIN, CAP_MIN = 26, 1.25, 6, 6, 9
FIXED_BOARD = {}   # правка 232: рамки паузы и паузы миссии (должны совпасть)
# 201 отменяет разрядку, 233 уменьшает Accept: текущий договор не пересекает буквы,
# заголовок <=14, подписи Swiss721 7px. Прежние 163 доступны как отдельный legacy режим.
LEGACY163 = bool(os.environ.get('UI_CHECK163_LEGACY'))
LETTER_GAP_MIN, TITLE_CAP_MAX, HINT_CAP_MIN = (2, 14, 9) if LEGACY163 else (0, 14, 7)
COLUMN_SCREENS = ('pause', 'pausemsn', 'pauseoptions', 'pausesound')
W, H = U.DST_W, U.DST_H
shots = Path(sys.argv[sys.argv.index('--shots') + 1]) if '--shots' in sys.argv else None
FC = U.FontCache('psp')


def letter_gaps(face, s):
    """просветы между соседними буквами строки s гранью face на PSP, px (по альфе >= 0.5; пробел — не просвет)"""
    g = FC.get(face)['glyphs']; out = []; pen = 0; prev = None
    for ch in s:
        gl = g.get(ord(ch)) or g[ord('?')]
        cols = np.where((gl['bm'] >= .5).any(0))[0] if gl['bm'] is not None else []
        if ch == ' ' or not len(cols):
            prev = None
        else:
            x0, x1 = pen + gl['left'] + cols[0], pen + gl['left'] + cols[-1] + 1
            if prev is not None:
                out.append(int(x0 - prev))
            prev = x1
        pen += gl['adv']
    return out


def ink(dl, bitmaps, state, sel=-1, bright=False):
    """(x0, y0, x1, y1) пикселей, которые рисует dl (альфа >= 128; bright — только светлые: буквы без тени)"""
    im = np.asarray(U.render(dl, W, H, state, bitmaps, Image.new('RGBA', (W, H), (0, 0, 0, 0)), None, sel))
    m = im[..., 3] >= 128
    if bright:
        m &= im[..., :3].max(2) >= 150
    ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
    return None if not len(xs) else (int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1)


def hide_dy(rows, hidden):
    """viewer/ui.c hideDy: строки ниже скрытой — вверх на её шаг, все — вниз на полшага"""
    ys = sorted(t['dst'][1] for t in rows)
    dy = {}
    for t in rows:
        d = 0
        for h in hidden:
            yh = h['dst'][1]; nxt = [y for y in ys if y > yh]; prv = [y for y in ys if y < yh]
            step = (nxt[0] - yh) if nxt else (yh - prv[-1]) if prv else 0
            if t['dst'][1] > yh: d -= step
            d += step // 2
        dy[id(t)] = d
    return dy


def screen(name):
    if name in M.PAGES and name not in ('viewcards', 'missionselect'):
        U.SCREEN_PAGES[name] = M.PAGES[name]
        pa, pf = U.Assets(), U.FontCache('psp')
        dl = M.build(name, pa, pf)
        st = {'show': M.TAGS[name]}
        for r in range(M.MAX_ROWS):
            st['ROW%d' % r] = 500 if any(t['type'] == U.T_BAR and t['field'] == 'ROW%d' % r for t in dl) else 1
        return dl, pa.bitmaps, st
    items, icons = U.build_items(name)
    pa, pf = U.Assets(), U.FontCache('psp')
    dl, _ = U.adapt(items, icons, 'psp', pa, pf)
    st = dict(U.DEMO_STATE); st['show'] = {'COINS'}
    return dl, pa.bitmaps, st


def check(name, view, dl, bm, st, fam):
    bad = []
    rows = [t for t in dl if t['type'] == U.T_TEXT and t.get('menu', -1) >= 0 and t['tag'] in st['show'] | {'ALWAYS'}]
    groups = {}
    for t in dl:
        if t.get('menu', -1) >= 0 or (t['field'].startswith('ROW') and t['type'] in (U.T_TEXT, U.T_BAR)):
            r = t['menu'] if t.get('menu', -1) >= 0 else int(t['field'][3:])
            groups.setdefault(r, []).append(t)
    for t in dl:                                              # ползунок: подложка дорожки и бегунок — к своей строке
        if t['type'] == U.T_IMG and t.get('slide'):
            groups.setdefault(t['slide'] - 1, []).append(t)
        if t['type'] == U.T_IMG and t['name'].endswith('_SliderBgd'):
            k = t['name'][:-len('_SliderBgd')]
            r = next((g for g, ts in groups.items() if any(x['name'] == k for x in ts)), None)
            if r is not None: groups[r].append(t)
    hidden = []
    if view == 'player':
        hidden = [t for t in rows if t['name'] in U.PAUSE_SERVICE_ROWS]
        dy = hide_dy(rows, hidden)
        for g in groups.values():
            for t in g:
                if t.get('menu', -1) >= 0 and id(t) in dy:
                    t['dst'] = [t['dst'][0], t['dst'][1] + dy[id(t)]] + list(t['dst'][2:])
        for h in hidden:
            groups.pop(h['menu'], None)
        dl = [t for t in dl if t not in hidden]
    page = next(t['page'] for t in dl if t['name'] == 'Frame_Top')
    board = ink([t for t in dl if t['page'] == page and t['name'] != 'Frame_Bgd'], bm, st)
    fill = next(t['dst'] for t in dl if t['page'] == page and t['name'] == 'Frame_Bgd')
    fill = (fill[0], fill[1], fill[0] + fill[2], fill[1] + fill[3])
    rb = []                                                   # (строка, буквы+картинки, верх строки подписи)
    for r in sorted(groups):
        g = groups[r]
        txt = [t for t in g if t['type'] == U.T_TEXT]
        b_txt = ink(txt, bm, st, sel=r, bright=True)                      # буквы (выбранная — жёлтая), без тени
        img = [t for t in g if t['type'] != U.T_TEXT]
        for t in [t for t in img if t.get('slide') and t.get('track')]:   # бегунок ползунка: крайние положения (viewer/ui.c fuse)
            for v in (0, 1000):
                sx = int(np.floor((v - 500) / 1000 * t['track'] + .5))
                img.append(dict(t, dst=[t['dst'][0] + sx] + list(t['dst'][1:])))
        b_img = ink(img, bm, st, sel=r) if img else None                  # стрелки, ползунок
        if b_txt is None:
            continue
        b = b_txt if b_img is None else (min(b_txt[0], b_img[0]), min(b_txt[1], b_img[1]), max(b_txt[2], b_img[2]), max(b_txt[3], b_img[3]))
        lab = next(t for t in txt if t.get('menu', -1) == r)
        lb = ink([lab], bm, st, sel=r, bright=True)
        if lb and lab['strings'] and lab['strings'][0].isupper() and lb[3] - lb[1] < CAP_MIN:   # подпись ПРОПИСНЫМИ — не мельче пунктов паузы
            bad.append('строка %d: подпись %r мелкая — заглавные %d px < %d' % (r, lab['strings'][0], lb[3] - lb[1], CAP_MIN))
        rb.append((r, b, lab['dst'][1]))
    rb.sort(key=lambda x: x[2])
    # 163: эти проверки раньше были описаны и определены, но никогда не вызывались.
    if name in COLUMN_SCREENS and abs(board[2] - board[0] - U.PAUSE_BOARD_W) > 1:
        bad.append('163 ширина: %d != постоянная %d px' % (board[2] - board[0], U.PAUSE_BOARD_W))
    for lab in rows:
        gaps = letter_gaps(lab['font'], lab['strings'][0]) if lab['strings'] else []
        if gaps and min(gaps) < LETTER_GAP_MIN:
            bad.append('163 буквы: %s просвет %d < %d' % (lab['name'], min(gaps), LETTER_GAP_MIN))
    column = page == 'XSmallBoard.pag' 
    tops = [ref for _, _, ref in rb]
    steps = [b - a for a, b in zip(tops, tops[1:])]
    info = 'строк %d, шаг %s, доска %s' % (len(rb), sorted(set(steps)), board and (board[0], board[1], board[2] - board[0], board[3] - board[1]))
    if len(set(steps)) > 1: bad.append('шаг строк неровный %s' % steps)
    pitch = steps[0] if steps else 0
    if column and view != 'service' and steps and pitch < PITCH_MIN: bad.append('шаг строк %d < %d (сжато)' % (pitch, PITCH_MIN))
    x0 = min(b[0] for _, b, _ in rb); x1 = max(b[2] for _, b, _ in rb); y0 = min(b[1] for _, b, _ in rb); y1 = max(b[3] for _, b, _ in rb)
    pt, pb, pl, pr = y0 - board[1], board[3] - y1, x0 - board[0], board[2] - x1
    gap = min(b[1] - a[3] for (_, a, _), (_, b, _) in zip(rb, rb[1:])) if len(rb) > 1 else 99
    info += ', поля сверху/снизу %d/%d, слева/справа %d/%d, просвет %d' % (pt, pb, pl, pr, gap)
    if view != 'service':
        if abs(pt - pb) > 1: bad.append('поля сверху/снизу %d/%d не равны' % (pt, pb))
        if abs(pl - pr) > 1: bad.append('поля слева/справа %d/%d не равны' % (pl, pr))
        ref = pitch if column else max(pitch, 24)
        # правка Роба 232 (03.10): пауза миссии — рамка постоянной высоты, как у паузы свободной езды (не по содержимому): её поля
        # сверху/снизу — сколько выйдет, лишь бы ровные; рамка обязана совпасть с рамкой паузы (FIXED_BOARD, ниже)
        if name != 'pausemsn' and max(pt, pb) > FIELD_MAX * ref: bad.append('поле %d > %.2f x шаг %d (рамка не по содержимому)' % (max(pt, pb), FIELD_MAX, ref))
        if name in ('pause', 'pausemsn') and board: FIXED_BOARD.setdefault(name, tuple(board))
        if min(pt, pb) < gap and len(rb) > 1: bad.append('поле %d меньше просвета строк %d' % (min(pt, pb), gap))
        if column:
            for r, b, _ in rb:
                c = (b[0] + b[2]) / 2; bc = (board[0] + board[2]) / 2
                if abs(c - bc) > 1: bad.append('строка %d не по центру доски (%.1f / %.1f)' % (r, c, bc))
    if gap < SEP_MIN: bad.append('строки налезают: просвет %d < %d' % (gap, SEP_MIN))
    fl, ft, fr_, fb_ = fill[0] - board[0], fill[1] - board[1], board[2] - fill[2], board[3] - fill[3]
    info += ', заливка от рамки %d/%d/%d/%d' % (fl, ft, fr_, fb_)
    if abs(fl - fr_) > 1 or abs(ft - fb_) > 1: bad.append('заливка доски кривая: слева/справа %d/%d, сверху/снизу %d/%d' % (fl, fr_, ft, fb_))
    inmin = IN_MIN
    if view == 'service':                                     # служебный режим (8 строк в рамке игрока): внутри рамки, не на ней
        fill = (board[0] + 8, board[1] + 8, board[2] - 8, board[3] - 8); inmin = 0
    for r, b, _ in rb:
        if b[0] - fill[0] < inmin or fill[2] - b[2] < inmin or b[1] - fill[1] < inmin or fill[3] - b[3] < inmin:
            bad.append('строка %d у края заливки доски %s / %s' % (r, b, fill))
    title = [t for t in dl if t['type'] == U.T_TEXT and t.get('menu', -1) < 0 and t['dst'][1] + t['dst'][3] <= board[1] + 2
             and t['tag'] in st['show'] | {'ALWAYS'}]
    tb = ink(title, bm, st, bright=True) if title else None
    if tb is None: bad.append('нет заголовка над доской')
    else:
        info += ', заголовок y %d..%d' % (tb[1], tb[3])
        if board[1] - tb[3] < 3: bad.append('заголовок налезает на рамку')
        coins = [t for t in dl if t['name'] == 'NumCoins']
        cb = ink(coins, bm, st) if coins else None
        if cb and not (cb[0] - tb[2] >= 8 or tb[0] - cb[2] >= 8 or cb[1] >= tb[3] or tb[1] >= cb[3]):
            bad.append('заголовок задевает счёт монет %s / %s' % (tb, cb))
    if tb and tb[3] - tb[1] > TITLE_CAP_MAX:
        bad.append('163 заголовок: %d > %d px' % (tb[3] - tb[1], TITLE_CAP_MAX))
    for pg in ('Accept.pag', 'Back.pag'):
        hints = [t for t in dl if t['page'] == pg]
        for t in hints:
            if t['type'] == U.T_TEXT:
                glyph = FC.get(t['font'])['glyphs'].get(ord('A'))
                ys = np.where((glyph['bm'] >= .5).any(1))[0] if glyph and glyph['bm'] is not None else []
                cap = int(ys[-1] - ys[0] + 1) if len(ys) else 0
                if cap < HINT_CAP_MIN:
                    bad.append('163 подписи (после233): %s заглавная %d < %d' % (pg, cap, HINT_CAP_MIN))
        hb = ink(hints, bm, st)
        if hb and not (hb[0] >= board[2] or hb[2] <= board[0] or hb[1] >= board[3] or hb[3] <= board[1]):
            bad.append('подсказка %s на доске' % pg)
        if hb and (hb[0] < 0 or hb[1] < 0 or hb[2] > W or hb[3] > H): bad.append('подсказка %s за экраном' % pg)
    if board[0] < 0 or board[1] < 0 or board[2] > W or board[3] > H: bad.append('доска за экраном %s' % (board,))
    if column and view != 'service':
        fam.append((name, board[2] - board[0], board[1]))
    if shots:
        im = U.render(dl, W, H, st, bm, U.backdrop(W, H, 'pause'), None, rb[0][0] if rb else -1)
        im.resize((W * 2, H * 2), Image.NEAREST).save(shots / ('%s_%s.png' % (name, view)))
    return bad, info


res, fam = [], []
for name, view in [('pause', 'player'), ('pause', 'service'), ('pausemsn', 'player'), ('pauseoptions', 'player'),
                   ('pausesound', 'player'), ('pausesettings', 'player')]:
    dl, bm, st = screen(name)
    try:
        bad, info = check(name, view, dl, bm, st, fam)
    except Exception as e:                                    # раскладка не та, что ждёт гейт (нет доски, строк) — тоже красное
        bad, info = ['разбор упал: %r' % e], ''
    res.append((name + ('' if view == 'player' else ' (служебный)'), bad, info))
if len({w for _, w, _ in fam}) > 1 or len({y for _, _, y in fam}) > 1:
    res.append(('семейство XSmallBoard', ['ширина/верх доски разные: %s' % fam], ''))
if not U.PAUSE_OLD and FIXED_BOARD.get('pause') and FIXED_BOARD.get('pausemsn') and FIXED_BOARD['pause'] != FIXED_BOARD['pausemsn']:
    res.append(('правка 232', ['рамка паузы миссии %s не равна рамке паузы %s (должна быть постоянной)' % (FIXED_BOARD['pausemsn'], FIXED_BOARD['pause'])], ''))
# Check the actual packed glyph cells, including scripts that build other menu packs.
if not os.environ.get('PAUSE_FONT_CHECK_OLD'):
    fontdir = sys.argv[sys.argv.index('--font-dir')+1] if '--font-dir' in sys.argv else str(ROOT/'build')
    fp = subprocess.run([sys.executable, str(ROOT/'tests/ui/menu_font_check.py'), '--dir', fontdir],
                        capture_output=True, text=True)
    fontbad = [] if fp.returncode == 0 else ['menu_font_check: ' + (fp.stdout+fp.stderr).strip().splitlines()[-1]]
    res.append(('menu_font_check', fontbad, 'попиксельная грань настоящих пакетов'))
ok = all(not b for _, b, _ in res)
print(('OK' if ok else 'FAIL') + ' · pause_layout' + (' (PAUSE_OLD)' if U.PAUSE_OLD else ''))
for n, b, info in res:
    print('  %-24s %s  %s' % (n, 'ok  ' if not b else 'FAIL', info))
    for x in b:
        print('      - ' + x)
sys.exit(0 if ok else 1)
