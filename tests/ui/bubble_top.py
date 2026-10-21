#!/usr/bin/env python3
"""Правка Роба 295 (04.10: «Talk to Marge опять по центру пузыря — верни как было: первая строка от скругления пилюли, с приличным
отступом от верхнего края»): по умолчанию текст задания HUD — у верха пузыря (раскладка до правки 215: строка во всю ширину, без
выравнивания по центру), первая строка начинается не выше верха видимого пузыря + 3 px и не ниже + 12 px (движок добавляет +3 px,
правка 156). КРАСНЫЙ: UI_OBJ_TEXT_CENTRE=1 (центр правки 215) обязан упасть. python3 tests/ui/bubble_top.py -> 0 = PASS"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U
items, icons = U.build_items('hud')
out, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
get = lambda n: next(t for t in out if t['name'] == n and t.get('tag') == 'OBJECTIVE')
box, msg = get('MessageBox'), get('Message')
bx, by, bw, bh = box['dst']; mx, my, mw, mh = msg['dst']
bim = U.all_images()[box['frames'][0]]; b0 = bim.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()[1]
vis0 = by + bh * b0 / bim.height
top = my + (3 if msg.get('valign') in (None, 'top', 0) else 0)   # +3 px — viewer/ui.c (правка 156) для текста у верха
bad = []
if msg.get('valign') == 'centre': bad.append('текст по центру пузыря (valign centre)')
if not (vis0 + 3 <= top <= vis0 + 12): bad.append(f'первая строка {top:.1f} px, верх пузыря {vis0:.1f} — отступ {top - vis0:.1f} вне 3..12')
print(f'верх пузыря {vis0:.1f}, первая строка {top:.1f} (отступ {top - vis0:.1f} px), valign {msg.get("valign")}')
print('PASS' if not bad else 'FAIL: ' + '; '.join(bad)); sys.exit(0 if not bad else 1)
