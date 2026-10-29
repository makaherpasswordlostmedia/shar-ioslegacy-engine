#!/usr/bin/env python3
"""Гейт рамки задания HUD (пузырь уведомлений слева): правки Роба 18, 22 и 48.
   python tests/missions/objective_gate.py             -> код 0 = зелёный
   UI_OBJ_WIDE=1 python tests/missions/objective_gate.py  отрицательный контроль: прежний пузырь шире под 16:9 -> обязан быть красным
   python tests/missions/objective_gate.py --plant       отрицательный контроль: подложен текст задания длиннее пузыря -> красный
Правка 48 (29.09, игра на PSP): «пузырь слишком широкий, будто растянут; текст иногда вылезает влево — вернуть ширину и поля
как в оригинале, текст всегда внутри». Раскладка PSP 480x272 — та же, что пишет tools/ui_export.py в ui.shr (build_items + adapt).
Проверки:
  1) аватар одного размера на всех этапах: все значки заданий миссий всех уровней (SetHUDIcon -> msnicons) одного размера;
  2) текст начинается сразу за самым широким значком при размере аватара правки 22: зазор 1..6 px;
  3) пузырь не растянут: пропорции MessageBox из Hud.pag (330x88) ±3 %, ширина не больше оригинала при общем масштабе
     рамки задания (R1 и множитель читаемости), без 3-среза вширь; не заходит на радар;
  4) текст внутри пузыря: левый край текста не левее пузыря, правый — не правее (поле справа = отступу сверху, viewer/ui.c
     fitW); КАЖДЫЙ текст задания этапа уровней 1–7 из библии (строки MISSION_OBJECTIVE_*) переносится по этой ширине и
     помещается в число строк пузыря (перенос — как viewer/ui.c wrapLines, ширины букв — как в пакете)."""
import importlib.util, os, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import ui_export as U

PLANT = '--plant' in sys.argv
items, icons = U.build_items('hud')
out, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
get = lambda n: next(t for t in out if t['name'] == n and t.get('tag') == 'OBJECTIVE')
icon, box, msg = get('ObjectiveIcon'), get('MessageBox'), get('Message')
radar = [t for t in out if t.get('tag') == 'RADAR']
ext = U.objective_icon_extent()
bad = []
# 1) размеры значков миссий
sizes = set(); used = set()
for f in (U.WEB / 'source/game/scripts/missions').glob('level0*/*.mfk'):
    used |= {m.lower() for m in re.findall(r'SetHUDIcon\s*\(\s*"([^"]*)"', f.read_text(errors='replace'))}
for p in (U.WEB / 'source/game/art/frontend/dynaload/images/msnicons').glob('*/*.p3d'):
    if p.stem.lower() in used:
        for c in U.read(p).children:
            if c.id == 0x19005: sizes.add(U.decode_sprite_image(c)[1].size)
if len(sizes) != 1: bad.append(f'значки заданий разного размера: {sorted(sizes)}')
# 2) текст сразу за аватаром (рамка аватара правки 22 — ext: x, y, w, h)
ax, ay, aw, ah = icon.get('extframe') or icon['dst']
bx, by, bw, bh = box['dst']; mx, my, mw, mh = msg['dst']
edge = ax + aw * ext; gap = mx - edge
print(f'аватар {aw}x{ah} px в x={ax}; самый широкий значок до {edge:.1f} px; текст с x={mx} (зазор {gap:.1f} px)')
if not 1 <= gap <= 6: bad.append(f'текст не сразу за аватаром: зазор {gap:.1f} px (нужно 1..6)')
# 3) пузырь в пропорциях оригинала
pg = U.project('ingame.p3d').pages['Hud.pag']
src = next(e for _, e in U.iter_leaves(pg) if e['name'] == 'MessageBox')
asp0, asp = src['w'] / src['h'], bw / bh
k = bh / (src['h'] * U.S)                                   # общий масштаб рамки задания по высоте (R1 x множитель читаемости)
rl = min((t['dst'][0] for t in radar), default=480)
print(f'пузырь x={bx}..{bx + bw} y={by} {bw}x{bh} px: пропорции {asp:.3f} (Hud.pag {src["w"]}x{src["h"]} = {asp0:.3f}), '
      f'масштаб {k:.3f}, ширина оригинала при нём {src["w"] * U.S * k:.1f} px; радар с x={rl}')
if abs(asp / asp0 - 1) > .03: bad.append(f'пузырь растянут: пропорции {asp:.3f} против {asp0:.3f} в Hud.pag')
if bw > src['w'] * U.S * k + 1.5: bad.append(f'пузырь шире оригинала: {bw} px > {src["w"] * U.S * k:.1f} px')
if any('_hs' in b for b in box.get('bitmaps', [])): bad.append('пузырь расширен 3-срезом (растянут вширь)')
if bx + bw > rl - 4: bad.append('пузырь заходит на радар')
# 4) текст внутри пузыря; все задания этапов уровней 1–7 помещаются
inset = my - by
right = min(mx + mw, bx + bw - inset); tw = right - mx
if mx < bx: bad.append(f'текст левее пузыря: x={mx} < {bx}')
if mx + mw > bx + bw: bad.append(f'рамка текста правее пузыря: {mx + mw} > {bx + bw}')
PIX8 = os.environ.get('UI_PIX8', '1') != '0'   # правка 126: текст задания рисуется гранью pix8 (msx 8×8, шаг 8, строка 10); 0 — шрифт пакета
if PIX8:
    lh = 10   # viewer/ui_layout.h PIX8_LH; шаг — pix8Adv: жирный компактный (уточнение Роба 01.10) — ширина рисунка + 1 px, пробел 3
    import re as _re
    _msx = bytes(int(v, 16) for v in _re.findall(r'0x([0-9a-fA-F]{2})', (ROOT / 'viewer/bootmsx.h').read_text().split('{', 1)[1]))
    _fix = {m[0]: [int(x, 16) for x in m[1].split(',')] for m in
            _re.findall(r"\{'(.)', \{([^}]*)\}\}", (ROOT / 'viewer/ui_layout.h').read_text())}   # pix8Fix — буквы руками
    def _adv(ch):
        c = ord(ch) if 32 <= ord(ch) <= 126 else ord('?')
        m = 0
        for y in range(8):
            r = _msx[c * 8 + y]
            m |= _fix[chr(c)][y] if chr(c) in _fix else (r | ((r >> 1) & ~(r << 1))) & 0xff   # = ui_layout.h pix8Row
        if c == 32 or not m: return 3
        a = next(x for x in range(8) if m & (0x80 >> x)); b = next(x for x in range(7, -1, -1) if m & (0x80 >> x))
        return b - a + 2
    adv = {}
    def lw(s): return sum(_adv(ch) for ch in s)
else:
    fc = U.FontCache('psp'); F = fc.get(msg['font']); lh = F['lh']
    adv = {c: int(g['adv']) for c, g in F['glyphs'].items()}
    def lw(s): return sum(adv.get(ord(ch), adv.get(ord('?'), 0)) for ch in s)
max_lines = max(1, (by + bh - inset - my) // lh)
SHORT = {'A', 'AN', 'THE', 'OF', 'OR', 'BUT', 'AND', 'NOR', 'TO', 'IN', 'ON', 'AT', 'BY', 'FOR', 'AS', 'IF', 'SO', 'INTO', 'ONTO', 'FROM',
         'WITH', 'THAN', 'YOUR', 'MY', 'IS', 'IT'}   # = viewer/ui_layout.h uiShortWord (№401)
SHORT_OLD = bool(os.environ.get('UI_WRAP_SHORT_OLD'))   # отрицательный контроль: прежний перенос — висящие слова есть
def wrap(s, maxw):   # = viewer/ui_layout.h uiWrap: '\\' и '\n' — жёсткий перенос (правка 126), дальше жадный по пробелам
    parts = s.replace('\\', '\n').split('\n')
    if len(parts) > 1: return [l for p in parts for l in wrap(p, maxw)]
    if lw(s) <= maxw: return [s]
    words, lines, cur = s.split(' '), [], None
    if not SHORT_OLD:   # №401 (= uiShortWord в uiWrapPara): короткое служебное слово склеено со следующим
        units = []
        for w in words:
            if units and units[-1].rpartition(' ')[2].upper() in SHORT: units[-1] += ' ' + w
            else: units.append(w)
        words = units
    for w in words:
        if cur is None: cur = w
        elif lw(cur + ' ' + w) <= maxw: cur += ' ' + w
        else: lines.append(cur); cur = w
    lines.append(cur or '')
    return lines
def hanging(ls): return sum(1 for x in ls[:-1] if x.rpartition(' ')[2].upper() in SHORT)
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
texts = {}
for lv in range(1, 8):
    c = mc.Compiler(lv); c.compile(); P = c.pack
    for st in P.stages:
        if st[4] != 0xFFFF and P.strings[st[5]]: texts.setdefault(P.strings[st[5]], f'L{lv} MISSION_OBJECTIVE_{st[4]:02d}')
if PLANT: texts['GO TO THE KWIK-E-MART AND BUY ENOUGH BUZZ COLA FOR THE WHOLE TOWN, THEN DRIVE IT HOME BEFORE MARGE NOTICES ANYTHING, '
                'AND THEN WATCH ITCHY AND SCRATCHY WITH BART AND LISA'] = 'plant'   # длиннее 4 строк и жирным компактным (126)
worst = (0, '', 0); hang = 0
for t, where in texts.items():
    ls = wrap(t, tw); wid = max(lw(x) for x in ls); hang += hanging(ls)
    if len(ls) > worst[0]: worst = (len(ls), where, wid)
    if len(ls) > max_lines or wid > tw: bad.append(f'{where}: {len(ls)} строк / шире {wid} px в пузыре {max_lines} строк x {tw} px: «{t[:48]}»')
if hang: bad.append(f'№401: строк, кончающихся коротким словом (of/or/but…): {hang}')
print(f'текст: {tw} px x {max_lines} строк (строка {lh} px); заданий этапов уровней 1–7: {len(texts)}, больше всего строк — {worst[0]} ({worst[1]}); висящих коротких слов {hang}')
for b in bad[:12]: print('  ', b)
print('ИТОГ:', 'зелёный' if not bad else f'КРАСНЫЙ ({len(bad)})')
sys.exit(1 if bad else 0)
