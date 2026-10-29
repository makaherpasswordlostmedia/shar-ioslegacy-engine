#!/usr/bin/env python3
"""Гейт правки Роба 215 (03.10): текст задания HUD — внутри пузыря по центру по высоте, переносы как на PS2; пузырь не двигается.
Роб: «текст внутри рамки выровнять, рамку не трогать; может идти во вторую строку — адаптивно, чтобы хорошо смотрелся на PSP».
   python3 tests/ui/objective_text.py                      -> код 0 = зелёный
   UI_OBJ_TEXT_TOP=1 python3 tests/ui/objective_text.py    -> прежняя раскладка (строка во всю ширину, прижата к верху): обязан быть красным
   UI_OBJ_WIDOW_OLD=1 python3 tests/ui/objective_text.py   -> перенос без правила висячего слова: обязан быть красным
Раскладка PSP 480x272 — та же, что пишет tools/ui_export.py в ui.shr; перенос и центр — как viewer/ui.c fitW / textGlyphs, буквы — грань
pix8 (msx 8x8, строка 10, шаг по букве), как в tests/missions/objective_gate.py.
Проверки:
  1) «COLLECT THE ICE CREAM AND COLA» — две строки, разрыв как на PS2 (запись bziOipI4gDI 3:19): «COLLECT THE ICE CREAM» / «AND COLA»;
  2) середина букв блока из одной строки («TALK TO APU») и из двух — в середине видимого пузыря ±1 px;
  3) каждый текст задания этапов уровней 1–7 помещается: строк не больше, чем вмещает пузырь, блок не выходит за видимый пузырь;
  4) пузырь на месте: его рамка совпадает с прежней раскладкой (UI_OBJ_TEXT_TOP=1, отдельный процесс)."""
import importlib.util, json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
if not os.environ.get('UI_OBJ_TEXT_TOP'): os.environ['UI_OBJ_TEXT_CENTRE'] = '1'   # правка 295: центр 215 — режимом, по умолчанию верх
import ui_export as U

items, icons = U.build_items('hud')
out, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
get = lambda n: next(t for t in out if t['name'] == n and t.get('tag') == 'OBJECTIVE')
box, msg = get('MessageBox'), get('Message')
bx, by, bw, bh = box['dst']; mx, my, mw, mh = msg['dst']
if '--box' in sys.argv:   # для проверки 4: рамка пузыря этой раскладки
    print(json.dumps([bx, by, bw, bh])); sys.exit(0)
bad = []
bim = U.all_images()[box['frames'][0]]
b0, b1 = bim.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()[1::2]
vis0, vis1 = by + bh * b0 / bim.height, by + bh * b1 / bim.height; cy = (vis0 + vis1) / 2
# грань pix8 (как tests/missions/objective_gate.py)
lh, cell = 10, 8
_msx = bytes(int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{2})', (ROOT / 'viewer/bootmsx.h').read_text().split('{', 1)[1]))
_fix = {m[0]: [int(x, 16) for x in m[1].split(',')] for m in
        re.findall(r"\{'(.)', \{([^}]*)\}\}", (ROOT / 'viewer/ui_layout.h').read_text())}
def adv(ch):
    c = ord(ch) if 32 <= ord(ch) <= 126 else ord('?'); m = 0
    for y in range(8):
        r = _msx[c * 8 + y]
        m |= _fix[chr(c)][y] if chr(c) in _fix else (r | ((r >> 1) & ~(r << 1))) & 0xff
    if c == 32 or not m: return 3
    a = next(x for x in range(8) if m & (0x80 >> x)); b = next(x for x in range(7, -1, -1) if m & (0x80 >> x))
    return b - a + 2
def lw(s): return sum(adv(ch) for ch in s)
WIDOW_OLD = bool(os.environ.get('UI_OBJ_WIDOW_OLD'))   # красный контроль: перенос без правила висячего слова
def wrap(s, maxw):   # = viewer/ui_layout.h uiWrap с битом UI_WRAP_NOWIDOW (текст задания)
    parts = s.replace('\\', '\n').split('\n')
    if len(parts) > 1: return [l for p in parts for l in wrap(p, maxw)]
    if lw(s) <= maxw: return [s]
    words, lines, cur = s.split(' '), [], None
    for w in words:
        if cur is None: cur = w
        elif lw(cur + ' ' + w) <= maxw: cur += ' ' + w
        else: lines.append(cur); cur = w
    lines.append(cur or '')
    if not WIDOW_OLD and len(lines) >= 2 and ' ' not in lines[-1] and ' ' in lines[-2]:
        head, word = lines[-2].rsplit(' ', 1)
        if lw(word + ' ' + lines[-1]) <= maxw: lines[-2:] = [head, word + ' ' + lines[-1]]
    return lines
inset = my - by                                     # = viewer/ui.c fitW: поле справа и снизу = отступу текста сверху
tw = min(bx + bw - inset - mx, mw); max_lines = max(1, (by + bh - inset - my) // lh)
va = msg.get('valign')
def block_mid(nl):   # = viewer/ui.c textGlyphs: y0 по valign, середина букв блока
    bhh = lh * nl
    y0 = my if va == 'top' else (my + mh - bhh if va == 'bottom' else my + (mh - bhh) // 2)
    return y0 + (lh * (nl - 1) + cell) / 2
print(f'пузырь {bx},{by} {bw}x{bh} px, видимый y {vis0:.1f}..{vis1:.1f} (середина {cy:.1f}); текст x={mx} y={my} {mw}x{mh} '
      f'valign={va}; строка до {tw} px, строк до {max_lines}')
# 1) переносы как на PS2
ice = wrap('COLLECT THE ICE CREAM AND COLA', tw)
print('  «COLLECT THE ICE CREAM AND COLA» ->', ' / '.join(ice))
if ice != ['COLLECT THE ICE CREAM', 'AND COLA']: bad.append(f'переносы не как на PS2: {ice}')
# 2) центр по высоте
for t in ('TALK TO APU', 'COLLECT THE ICE CREAM AND COLA'):
    nl = len(wrap(t, tw)); m = block_mid(nl)
    print(f'  «{t}»: {nl} стр., середина букв {m:.1f} (пузырь {cy:.1f})')
    if abs(m - cy) > 1.01: bad.append(f'«{t}» не по центру пузыря: {m:.1f} против {cy:.1f}')
# 3) все задания уровней 1–7
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
texts = {}
for lv in range(1, 8):
    c = mc.Compiler(lv); c.compile(); P = c.pack
    for st in P.stages:
        if st[4] != 0xFFFF and P.strings[st[5]]: texts.setdefault(P.strings[st[5]], f'L{lv} MISSION_OBJECTIVE_{st[4]:02d}')
most = 0
for t, where in texts.items():
    ls = wrap(t, tw); nl = len(ls); most = max(most, nl); m = block_mid(nl)
    top, bot = m - (lh * (nl - 1) + cell) / 2, m + (lh * (nl - 1) + cell) / 2
    if nl > max_lines or max(lw(x) for x in ls) > tw: bad.append(f'{where}: {nl} строк в пузыре на {max_lines}: «{t[:40]}»')
    elif top < vis0 + 1 or bot > vis1 - 1: bad.append(f'{where}: блок {top:.0f}..{bot:.0f} вне пузыря {vis0:.0f}..{vis1:.0f}: «{t[:40]}»')
print(f'  заданий этапов уровней 1–7: {len(texts)}, больше всего строк — {most}')
# 4) пузырь на месте
env = dict(os.environ, UI_OBJ_TEXT_TOP='1')
old = json.loads(subprocess.run([sys.executable, __file__, '--box'], env=env, capture_output=True, text=True).stdout.strip().splitlines()[-1])
print(f'  пузырь прежней раскладки {old}')
if old != [bx, by, bw, bh]: bad.append(f'пузырь сдвинут: {[bx, by, bw, bh]} против прежнего {old}')
for b in bad[:12]: print('  ', b)
print('ИТОГ:', 'зелёный' if not bad else f'КРАСНЫЙ ({len(bad)})')
sys.exit(1 if bad else 0)
