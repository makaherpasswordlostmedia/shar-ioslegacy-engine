#!/usr/bin/env python3
"""Гейт правки Роба 255 (03.10 17:00, поверх 243): экран прав Fox — «верни как было и потяни пропорционально на 4 пикселя вниз».
Содержимое лицензии (tools/load_export.py lic_rect) — прежний масштаб S (как до 243), пропорционально увеличенный так, что по
высоте на экране PSP прибавилось LIC_PLUS_PX = 4 px; верх содержимого и середина по ширине — на прежнем месте.
   python3 tests/ui/license_plus4.py                  -> код 0 = зелёный
   UI_LIC_FILL=1 python3 tests/ui/license_plus4.py    -> правка 243 (вписать в 88 % экрана, ×1,33): обязан быть красным
   UI_LIC_OLD=1 python3 tests/ui/license_plus4.py     -> как до 243 (+0 px): обязан быть красным
Проверки по макетам, как увидит GE (load_export.mock), против прежнего (UI_LIC_OLD=1, отдельный процесс):
  1) высота содержимого больше прежней на 3..5 px (4 ± 1 на округление), ширина — пропорционально (±2 px);
  2) верх содержимого и середина по ширине на месте (±1 px), содержимое не у края кадра;
  3) на экране BootupLoad текст лицензии закрыт, логотип на месте лицензии (±1 px)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


def measure():
    import load_export as L
    res = L.export('boot', os.path.join(tempfile.mkdtemp(), 'boot.shr'), mocks=False)
    lic = np.asarray(L.mock(res, 'license', {}).convert('RGB')).astype(int)
    bld = np.asarray(L.mock(res, 'bootload', {}).convert('RGB')).astype(int)
    ys, xs = np.where(lic.sum(2) > 90)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    cut = y0 + (y1 - y0) // 3                      # логотип — верхняя треть содержимого, ниже — строки текста
    txt = lic[cut:].sum(2) > 200; tb = bld[cut:].sum(2) > 200
    lb = np.where((bld[202:].sum(2) > 200).any(1))[0]; ld_top = 202 + int(lb.min()) if len(lb) else 272   # надпись LOADING
    leak = int((tb & txt)[: max(0, ld_top - 2 - cut)].sum())
    lg_l = np.where((lic[:cut].sum(2) > 90).any(1))[0]; lg_b = np.where((bld[:cut].sum(2) > 90).any(1))[0]
    logo_dy = abs(int(lg_l.min()) - int(lg_b.min())) if len(lg_b) else 99
    return dict(x0=x0, x1=x1, y0=y0, y1=y1, leak=leak, logo_dy=logo_dy)


if '--measure' in sys.argv:
    print('MEASURE ' + json.dumps(measure())); sys.exit(0)
env = {**os.environ, 'UI_LIC_OLD': '1'}; env.pop('UI_LIC_FILL', None)
out = subprocess.run([sys.executable, __file__, '--measure'], env=env, capture_output=True, text=True).stdout
ref = json.loads([l for l in out.splitlines() if l.startswith('MEASURE ')][-1][8:])
cur = measure()
h0, h1 = ref['y1'] - ref['y0'] + 1, cur['y1'] - cur['y0'] + 1
w0, w1 = ref['x1'] - ref['x0'] + 1, cur['x1'] - cur['x0'] + 1
c0, c1 = (ref['x0'] + ref['x1']) / 2, (cur['x0'] + cur['x1']) / 2
print(f'прежнее (до 243): x {ref["x0"]}..{ref["x1"]} ({w0} px), y {ref["y0"]}..{ref["y1"]} ({h0} px)')
print(f'сейчас:           x {cur["x0"]}..{cur["x1"]} ({w1} px), y {cur["y0"]}..{cur["y1"]} ({h1} px); по высоте {h1 - h0:+d} px, '
      f'по ширине {w1 - w0:+d} px (пропорционально {(h1 - h0) * w0 / h0:+.1f})')
bad = []
if not 3 <= h1 - h0 <= 5: bad.append(f'высота {h1 - h0:+d} px, нужно +4 ± 1')
if abs((w1 - w0) - (h1 - h0) * w0 / h0) > 2: bad.append(f'ширина {w1 - w0:+d} px — не пропорционально')
if abs(cur['y0'] - ref['y0']) > 1: bad.append(f'верх содержимого сдвинулся: {ref["y0"]} -> {cur["y0"]}')
if abs(c1 - c0) > 1: bad.append(f'середина по ширине сдвинулась: {c0:.1f} -> {c1:.1f}')
if cur['x0'] < 1 or cur['x1'] > 478 or cur['y0'] < 1 or cur['y1'] > 270: bad.append('содержимое у самого края кадра')
print(f'BootupLoad: светлых пикселей текста под закрышкой {cur["leak"]}, логотип против лицензии {cur["logo_dy"]} px')
if cur['leak'] > 20: bad.append(f'текст лицензии виден на BootupLoad: {cur["leak"]} px')
if cur['logo_dy'] > 1: bad.append('логотип на BootupLoad не на месте лицензии')
for b in bad: print('  ', b)
print('ИТОГ:', 'зелёный' if not bad else f'КРАСНЫЙ ({len(bad)})')
sys.exit(1 if bad else 0)
