#!/usr/bin/env python3
"""Разбор гейта радара (правка Роба 50, tests/ui/radar_emu.sh): снимки окна эмулятора + строки RADAR движка.
Эталон PS2 (CATALOG_L1 «Радар», кадры 4:25…28:20): светлый клин от центра к синей точке цели; цель за краем — точка на
ободе, клин до обода; телефон, магазин, раздатчики — только в пределах радара (у обода висит только цель).
По снимкам (независимо от кода): центр радара — середина зелёного диска, синяя точка цели, пиксели клина (жёлто-зелёные,
g > 150, 90 < r < 170, b < 90) — направление клина = направлению на точку (±20°); на radar_far точка у обода (≥ 0.8 радиуса).
По строкам RADAR: rimother = 0 (у обода ничего, кроме целей), клин есть (cone=1).
  radar_check.py OUTDIR [--expect-red]"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
out = Path(sys.argv[1]); red = '--expect-red' in sys.argv
fails, notes = [], []
def radar(name):
    p = out / f'{name}.png'
    if not p.exists(): fails.append(f'нет снимка {name}'); return None
    im = Image.open(p).convert('RGB'); w, h = im.size
    a = np.asarray(im.crop((int(w * .78), int(h * .64), int(w * .97), int(h * .97)))).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cx, cy, R = CX * a.shape[1], CY * a.shape[0], RR * a.shape[1]   # HUD неподвижен: круг радара — постоянный
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]; inside = np.hypot(xx - cx, yy - cy) < R
    wedge = (g > 150) & (r > 90) & (r < 170) & (b < 90) & inside
    blue = (b > 140) & (r < 60) & (g < 90) & inside
    res = dict(cx=cx, cy=cy, R=R, nw=int(wedge.sum()), nb=int(blue.sum()))
    if blue.sum() >= 12:
        by, bx = np.nonzero(blue); res['dot'] = (bx.mean() - cx, by.mean() - cy)
    if wedge.sum() >= 40:
        wy, wx = np.nonzero(wedge); res['wedge'] = (wx.mean() - cx, wy.mean() - cy)
    return res
# круг радара в вырезе окна (w*.78…w*.97, h*.64…h*.97) при окне 1920x1152: центр 172, 182.5, радиус диска 102 px (замер
# чистого снимка radar_near 29.09 по зелёному диску) — доли выреза, чтобы не зависеть от масштаба окна
CX, CY, RR = 172.3 / 365, 182.5 / 380, 102.0 / 365
ang = lambda v: np.degrees(np.arctan2(v[0], -v[1]))
for name in ('radar_near', 'radar_far'):
    q = radar(name)
    if not q: continue
    if 'dot' not in q: fails.append(f'{name}: синей точки цели нет'); continue
    if 'wedge' not in q: fails.append(f'{name}: клина нет ({q["nw"]} px)'); continue
    da = (ang(q['wedge']) - ang(q['dot']) + 180) % 360 - 180
    dd = np.hypot(*q['dot']) / q['R']
    notes.append(f'{name}: на точку {ang(q["dot"]):.0f}°, клин {ang(q["wedge"]):.0f}° (разница {da:+.0f}°), точка на {dd:.2f} радиуса')
    if abs(da) > 20: fails.append(f'{name}: клин смотрит не на цель (разница {da:+.0f}°)')
    if name == 'radar_far' and dd < .8: fails.append(f'radar_far: цель за краем, а точка не у обода ({dd:.2f} радиуса)')
rows = [l for l in (out / 'smoke.txt').read_text(errors='replace').splitlines() if l.startswith('RADAR ')] if (out / 'smoke.txt').exists() else []
if not rows: fails.append('нет строк RADAR (flag radarlog)')
else:
    kv = [dict(re.findall(r'(\w+)=([-\d.,]+)', l)) for l in rows]
    ro = max(int(k['rimother']) for k in kv)
    if ro: fails.append(f'у обода висят не цели: до {ro} значков (rimother)')
    if not any(k['cone'] == '1' for k in kv): fails.append('движок не рисовал клин ни разу (cone=0)')
    notes.append(f'RADAR: {len(rows)} строк, у обода не-целей максимум {ro}')
for n in notes: print('  ' + n)
if red:
    print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман)'); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print('OK: клин к цели, цель за краем — у обода, прочие значки у обода не висят')
