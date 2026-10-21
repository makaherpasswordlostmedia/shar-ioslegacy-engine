#!/usr/bin/env python3
"""№398: гладкая тень (без полутона №394) на настоящих кадрах сцены shadow394 (tests: build/twins/scen/full/<прогон>).
Три условия на дороге у ног Гомера (неподвижная камера, кадры stipple0/stipple1 через 0,5 с, old = прежняя мягкая тень без
смещения глубины): (1) не мигает — кадры 0 и 1 равны пиксель в пиксель; (2) нет зерна — разница «чётных» и «нечётных» пикселей
(шахматка) такая же, как у мягкой тени old (сама текстура дороги и дизеринг дают ~10–20; полутон добавляет ~40), допуск 6;
(3) тень той же темноты, что прежняя мягкая (|разница| ≤ 12).
Красный: сборка -DGROUND_SHADE_HALFTONE=1 (полутон №394) обязана упасть на (2).
  python3 tests/ui/ground_shade.py build/twins/scen/full/rob398_new"""
import sys
from pathlib import Path
from PIL import Image
p = Path(sys.argv[1])
assert 'END' in (p / 'smoke.txt').read_text(), 'scene incomplete'
a, b, old = [Image.open(p / f'{s}.png').convert('RGB') for s in ('stipple0', 'stipple1', 'old')]
assert all(im.size == (480, 272) for im in (a, b, old)), 'must be native PSP pixels'
box = (248, 174, 256, 181)   # дорога у ног, вне анимированного персонажа (как гейт №394)
par = [[], []]; opar = [[], []]; old_sum = []; flick = 0
for y in range(box[1], box[3]):
    for x in range(box[0], box[2]):
        av, bv, ov = a.getpixel((x, y)), b.getpixel((x, y)), old.getpixel((x, y))
        flick += av != bv; par[(x + y) & 1].append(sum(av)); opar[(x + y) & 1].append(sum(ov)); old_sum.append(sum(ov))
m0, m1 = sum(par[0]) / len(par[0]), sum(par[1]) / len(par[1]); mean = (m0 + m1) / 2; om = sum(old_sum) / len(old_sum)
o0, o1 = sum(opar[0]) / len(opar[0]), sum(opar[1]) / len(opar[1])
bad = []
if flick: bad.append(f'мигает: {flick} пикселей отличаются через 0,5 с')
if abs(abs(m0 - m1) - abs(o0 - o1)) > 6: bad.append(f'зерно: чётные/нечётные {m0:.1f}/{m1:.1f} против мягкой {o0:.1f}/{o1:.1f}')
if abs(mean - om) > 12: bad.append(f'темнота {mean:.1f} против прежней мягкой {om:.1f}')
print(('FAIL ' + '; '.join(bad)) if bad else f'PASS ровная тень: 0 мигающих из {len(old_sum)}, чётные/нечётные {m0:.1f}/{m1:.1f}, темнота {mean:.1f} (прежняя мягкая {om:.1f})')
sys.exit(1 if bad else 0)
