#!/usr/bin/env python3
"""Сверка будки (прогон tests/shop/booth_scenario.txt) с записью PS2 ps2_v105_booth_access (пункт ДОБИВКИ 26):
  галерея L1 — 6 строк в порядке PS2 (Family Sedan, Electaurus, Pickup Truck, Plow King, Duff Truck, Surveillance Van);
  ► со своей машины — Electaurus, закрыт (строка PHONEV sel ... owned=0).
  Звёзды и Accept — по снимкам, не по строкам лога флаговых функций (boothShowStats / boothShowAccept):
  · звёзды: в клетках звёзд пакета build/phone.shr (картинки STREETRACE, ROW4..7 по 5 клеток) снимка ph_locked считываются
    полузвёзды строк по цвету (полная — жёлтая клетка, половина — вполовину, пустая — рисунок без жёлтого) и сверяются с
    build/phonecars.txt для elect_v (SetCarAttributes диска, PS2 shot_50: 2 / 1.5 / 1.5 / 4). Тот же разбор на ph_own (своя famil_v,
    звёзды видны и в старом коде) обязан дать её строку phonecars — проверка самого разбора;
  · Accept: у закрытой (ph_locked) в углу подсказок светлого меньше, чем у своей (ph_own).
  access_booth_check.py RUN_DIR [--expect-fail]   -> первая строка итог"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/ui'))
import booth_layout as BL   # noqa: E402  чтение пакета UIP1 (что видит движок)

run = Path(sys.argv[1]); expfail = '--expect-fail' in sys.argv
log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
pl = [l for l in log if l.startswith('PHONEV')]
if not pl: print('FAIL прогон: нет строк PHONEV'); sys.exit(2)
PS2 = 'famil_v,elect_v,cletu_v,plowk_v,cDuff,cVan'
bad = []
op = next((l for l in pl if l.startswith('PHONEV open')), '')
m = re.search(r'open n=(\d+) .* list=(\S+)', op)
if not m or m.group(1) != '6' or m.group(2) != PS2: bad.append('галерея не как PS2 (%s)' % (op.split(' t=')[0] or 'нет open'))
sel = next((l for l in pl if l.startswith('PHONEV sel')), '')
if not re.match(r'PHONEV sel 1 name=elect_v owned=0 ', sel): bad.append('► не закрытый Electaurus (%s)' % sel.split(' t=')[0])


# клетки звёзд из пакета; пороги разбора цвета — по клеткам ph_own (своя машина, звёзды рисуются и в старом коде): полная клетка
# 15×15 даёт жёлтого ~0.07, половина ~0.04, пустая 0 при рисунке (не синий фон) ~0.08 — разделители посередине
CELLS = sorted([t for t in BL.items(ROOT / 'build/phone.shr') if t['type'] == BL.U.T_IMG and t['tag'] == 'STREETRACE'],
               key=lambda t: (t['field'], t['x']))
CARS = {l.split()[0]: [int(v) for v in l.split()[2:6]] for l in (ROOT / 'build/phonecars.txt').read_text().splitlines() if len(l.split()) == 6}


def stars(name):   # снимок -> [полузвёзды ROW4..7] или None (клетка без рисунка звезды — звёзд нет)
    p = run / f'{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('RGB').resize((480, 272))).astype(int)
    out = []
    for f in ('ROW4', 'ROW5', 'ROW6', 'ROW7'):
        v = 0
        for t in [c for c in CELLS if c['field'] == f]:
            c = a[t['y']:t['y'] + t['h'], t['x']:t['x'] + t['w']]; R, G, B = c[..., 0], c[..., 1], c[..., 2]
            yel = ((R > 150) & (G > 110) & (B < 120)).mean(); ink = ((B - R) < 15).mean()
            if ink < 0.04: return None
            v += 2 if yel > 0.055 else 1 if yel > 0.02 else 0
        out.append(v)
    return out


if len(CELLS) != 20: bad.append('в build/phone.shr клеток звёзд %d, ждали 4×5' % len(CELLS))
else:
    so, sl = stars('ph_own'), stars('ph_locked')
    if so != CARS.get('famil_v'): bad.append('разбор звёзд на своей famil_v %s, phonecars %s — разбор не годен' % (so, CARS.get('famil_v')))
    elif sl != CARS.get('elect_v'): bad.append('звёзды закрытого Electaurus на снимке %s, phonecars/PS2 %s' % (sl or 'нет', CARS.get('elect_v')))


def accept_ink(name):   # доля светлых пикселей в нижнем правом углу, где стопка подсказок Accept/Back (правка 141)
    p = run / f'{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('L').resize((480, 272))).astype(int)[200:272, 300:480]
    return float((a > 200).mean())


lk, ow = accept_ink('ph_locked'), accept_ink('ph_own')
if lk is None or ow is None: bad.append('нет снимков ph_locked/ph_own')
elif not ow > lk + 0.005: bad.append('на снимке у закрытой подсказок не меньше, чем у своей (%.4f против %.4f)' % (lk, ow))
info = 'светлых в углу подсказок: закрытая %.4f, своя %.4f; звёзды на снимке: закрытая %s, своя %s' % (lk or -1, ow or -1, stars('ph_locked'), stars('ph_own'))
if expfail:
    print(('OK красный пойман: ' + '; '.join(bad)) if bad else 'FAIL красный не пойман (' + info + ')'); sys.exit(0 if bad else 1)
print(('OK будка как PS2: ' + PS2 + '; ' + info) if not bad else 'FAIL ' + '; '.join(bad) + ' (' + info + ')')
sys.exit(1 if bad else 0)
