#!/usr/bin/env python3
"""Сверка прогона tests/shop/emu.sh: строки SHOPV (viewer/shop_view.c) и снимки окна.
  emu_check.py ОТЧЁТ [1]   1 — отрицательный прогон (flag shopvoff): PASS, только если сверка упала"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

out, neg = Path(sys.argv[1]), len(sys.argv) > 2 and sys.argv[2] == '1'
log = (out / 'smoke.txt').read_text(errors='replace') if (out / 'smoke.txt').exists() else ''
sv = [l for l in log.splitlines() if l.startswith('SHOPV')]
fails = []


def has(pat): return any(re.search(pat, l) for l in sv)


def frac(name, box, cond):
    p = out / f'{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('RGB').resize((480, 288))).astype(int)[16:, :][box[1]:box[3], box[0]:box[2]]   # без заголовка окна
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return float(cond(r, g, b).mean())


red = lambda r, g, b: (r > 110) & (g < 80) & (b < 70) & (r > g * 1.6)          # шторы
green = lambda r, g, b: (g > 110) & (r < 110) & (b < 120) & (g > r * 1.3)       # подиум и колонны
opened = has(r'^SHOPV open seller=\d+ item=\d+ coins=200 name=plowk_v')
if not opened: fails.append('лавка Барни не открыла экран покупки (нет строки SHOPV open ... plowk_v)')
if not has(r'^SHOPV idle'): fails.append('свет не зажёгся (нет SHOPV idle)')
if not has(r'^SHOPV stats=1'): fails.append('□ не показал звёзды (нет SHOPV stats=1)')
if not has(r'^SHOPV buy item=\d+ price=150 coins=50 name=plowk_v'): fails.append('✕ не купил Plow King за 150 (нет SHOPV buy ... coins=50)')
if not has(r'^SHOPV commit item=\d+ r=0 coins=50'): fails.append('покупка не засчитана после экрана (нет SHOPV commit r=0 coins=50)')
if not has(r'^SHOPV end coins=50 open=0'): fails.append('экран не закрылся после покупки (нет SHOPV end coins=50 open=0)')
if not has(r'^SHOPV open .*name=cDuff'): fails.append('лавка Гила не открылась (Duff Truck первым)')
if not has(r'^SHOPV sel item=\d+ name=cVan'): fails.append('► у Гила не показал фургон (нет SHOPV sel ... cVan)')
if not has(r'^SHOPV cancel'): fails.append('△ у Гила не отказал (нет SHOPV cancel)')
v = {}
for n in ('shop_dark', 'shop_lit', 'shop_stats', 'shop_after', 'gil_van'):
    v[n] = (frac(n, (60, 30, 420, 170), red), frac(n, (120, 170, 360, 256), green))
if any(x is None for p in v.values() for x in p): fails.append('нет снимков: ' + ', '.join(n for n, p in v.items() if p[0] is None))
else:
    if v['shop_lit'][0] < .12 or v['shop_lit'][1] < .05: fails.append('на снимке shop_lit нет сцены подиума (шторы %.3f, зелёное %.3f)' % v['shop_lit'])
    if v['gil_van'][0] < .12: fails.append('у Гила нет сцены подиума (шторы %.3f)' % v['gil_van'][0])
    if v['shop_dark'][0] >= v['shop_lit'][0] * .8: fails.append('свет не зажигается: тёмная %.3f, светлая %.3f' % (v['shop_dark'][0], v['shop_lit'][0]))
    if v['shop_after'][0] > .06: fails.append('после покупки экран не ушёл (шторы %.3f)' % v['shop_after'][0])
line = '; '.join('%s шторы %.3f зелёное %.3f' % (n, *p) for n, p in v.items() if p[0] is not None)
if neg:
    print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман): ' + line); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0] + ' [' + line + ']'); sys.exit(1)
print('OK: экран покупки у Барни и Гила (%d строк SHOPV); %s; снимки %s' % (len(sv), line, out))
