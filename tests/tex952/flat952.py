#!/usr/bin/env python3
"""Гейт №952 (хост, без эмулятора): стены с почти однотонной текстурой уходят в заливку, остальное не трогается.
  tests/tex952/flat952.py НАБОР [ВЫХОД_ДАННЫХ]    НАБОР — папка с level.shr (L1) и l2…l7/level.shr, рядом notoon.txt и flat912.bin выпуска (как в tests/toon/flat929.py)
Независимая проверка: разброс цвета текстуры считается по пикселям картинки (не по палитре, как в правиле), потом сверяется с тем, что сделало правило.
  1) данные выпуска (flat912.bin) побайтно = выход прежних правил (WALL952_OLD=1): база та же
  2) каждая текстура, перешедшая из рисунка в заливку, была причиной 10 (стена с рисунком №929) и имеет разброс ≤ порога; 3) каждая причина-10 с разбросом ≤ порога перешла (полнота)
  4) ничего больше не изменилось: заливка не стала рисунком, другие причины не тронуты; 5) перешло не меньше 10 текстур на 7 уровнях
Красный контроль: WALL952_OLD=1 (правило выключено) — гейт обязан упасть (проверка 5). Данные уровней пишутся в ВЫХОД_ДАННЫХ (L1 в корне, остальные в lN/)"""
import sys, os
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'tools'))
import flat_list as F
pk = Path(sys.argv[1]); outd = Path(sys.argv[2]) if len(sys.argv) > 2 else None
red = os.environ.get('WALL952_OLD') == '1'
bad = 0; flips_all = 0
for n in range(1, 8):
    d = pk if n == 1 else pk / f'l{n}'; lv = d / 'level.shr'
    if not lv.exists(): print(f'L{n}: нет level.shr'); bad += 1; continue
    nt = d / 'notoon.txt'; nt = str(nt if nt.exists() else pk / 'notoon.txt')
    F.WALL952_OLD = True; old, rows_old, sig = F.build(str(lv), nt)
    F.WALL952_OLD = red; new, rows_new, sig2 = F.build(str(lv), nt)
    ship = d / 'flat912.bin'
    if ship.exists() and ship.read_bytes() != old: print(f'L{n}: ОШИБКА flat912.bin выпуска не совпал с выходом прежних правил'); bad += 1
    f, tex, _ = F.load_level(str(lv)); flips = []; wrong = []
    for i, ((ko, wo), (kn, wn)) in enumerate(zip(rows_old, rows_new)):
        if (ko, wo) == (kn, wn): continue
        if ko == 0 and kn == 1 and wo == 10: flips.append(i)
        else: wrong.append((i, (ko, wo), (kn, wn)))
    def spread(i):
        t = tex[i]; px = F.indices(f, t); pal = t['pal']; rgb = pal[px][:, :, :3].astype(float); al = pal[px][:, :, 3] >= 16
        m = rgb[al].mean(axis=0); return float(np.abs(rgb[al] - m).mean())
    over = [(i, round(spread(i), 2)) for i in flips if spread(i) > F.FLAT952_E1 + 0.01]
    missed = [i for i, (k, w) in enumerate(rows_old) if w == 10 and k == 0 and not tex[i]['ground'] and spread(i) <= F.FLAT952_E1 - 0.01 and rows_new[i][0] != 1]
    print(f'L{n}: в заливку перешло {len(flips)} (≤ {F.FLAT952_E1}): {flips[:40]}' + (f'  ОШИБКА выше порога {over}' if over else '') + (f'  ОШИБКА не перешли {missed}' if missed else '') + (f'  ОШИБКА лишние изменения {wrong}' if wrong else ''))
    bad += len(over) + len(missed) + len(wrong); flips_all += len(flips)
    if outd is not None:
        o = outd if n == 1 else outd / f'l{n}'; o.mkdir(parents=True, exist_ok=True); (o / 'flat912.bin').write_bytes(new)
if flips_all < 10: print(f'ОШИБКА перешло всего {flips_all} текстур (нужно ≥ 10)'); bad += 1
print(f'всего перешло {flips_all}'); print('PASS' if not bad else 'FAIL'); sys.exit(0 if not bad else 1)
