#!/usr/bin/env python3
"""Сверка прогона tests/missions/collect_fx.sh: эффект цели SetCollectibleEffect и пятно маркера цели <рисунок>_shadow.

  python3 tests/missions/collect_fx_check.py RUN_GOTO RUN_RACE [--base RUN_GOTO_OLD RUN_RACE_OLD]

RUN_* — папки безголового прогона (smoke.txt, *.png). Ждём (запись PS2 10:34.1–10:34.8 и 5:21, 5:32):
  goto (m2 этап 9, сфера у дома Фландерса, SetCollectibleEffect("wrench_collect")):
    * строка «MSN marker carsphere shadow=carsphere_shadow» — под сферой рисуется кольцо на земле;
    * «MSN cfx wrench_collect goto=9 ... parts=N», N >= 2 (система частиц + квады), у машины игрока (не в центре локатора
      264.1, 173.9 — объём цели 44 x 72 м), и «MSN cfx-sprites K», K > 0 — квады отданы на рисование;
  race (sr1, точка гонки — предмет AddCollectible с эффектом): «MSN cfx wrench_collect item=0 ... parts>=2».
С --base (тот же сценарий с флагами cfxold 1 / mkshadowold 1) ещё пиксели: кадр сразу после въезда (fx_a / r_c) и кадр
подъезда (ap_b / r_a) отличаются от прежнего голубым светом (пикселей, где B выросла > 30, больше порога).
Код 0 — всё сошлось, 1 — нет."""
import argparse, re, sys
from pathlib import Path
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument('goto'); ap.add_argument('race'); ap.add_argument('--base', nargs=2)
a = ap.parse_args()
fails = []


def log(d): return (Path(d) / 'smoke.txt').read_text(errors='replace')


g = log(a.goto)
m = re.search(r'^MSN marker carsphere shadow=(\S+)', g, re.M)
if not m or m.group(1) != 'carsphere_shadow': fails.append(f'goto: маркер сферы без кольца ({m.group(1) if m else "нет строки MSN marker"})')
m = re.search(r'^MSN cfx wrench_collect goto=9 at=([-\d.]+),([-\d.]+),([-\d.]+) parts=(\d+)', g, re.M)
if not m: fails.append('goto: нет строки MSN cfx wrench_collect goto=9')
else:
    x, z, n = float(m.group(1)), float(m.group(3)), int(m.group(4))
    if n < 2: fails.append(f'goto: эффект не запущен (parts={n})')
    if abs(x - 264.1) + abs(z - 173.9) < 1.: fails.append('goto: эффект в центре локатора, а не у машины')
m = re.search(r'^MSN cfx-sprites (\d+)', g, re.M)
if not m or int(m.group(1)) <= 0: fails.append('goto: квады эффекта не рисовались (нет MSN cfx-sprites > 0)')
r = log(a.race)
m = re.search(r'^MSN cfx wrench_collect item=0 at=\S+ parts=(\d+)', r, re.M)
if not m or int(m.group(1)) < 2: fails.append(f'race: эффект точки гонки не запущен ({m.group(0) if m else "нет строки"})')
m = re.search(r'^MSN marker carsphere shadow=(\S+)', r, re.M)
if not m or m.group(1) != 'carsphere_shadow': fails.append('race: точка гонки без кольца на земле')


def bluer(new, old, box=None):
    A = np.asarray(Image.open(new).convert('RGB'), np.int16); B = np.asarray(Image.open(old).convert('RGB'), np.int16)
    if box: A, B = A[box[1]:box[3], box[0]:box[2]], B[box[1]:box[3], box[0]:box[2]]
    return int(((A[..., 2] - B[..., 2]) > 30).sum())


if a.base:
    for (run, base, shot, need, what) in ((a.goto, a.base[0], 'ap_b', 45, 'кольцо под сферой (подъезд)'),
                                          (a.goto, a.base[0], 'fx_a', 400, 'вспышка въезда в сферу'),
                                          (a.race, a.base[1], 'r_a', 60, 'кольцо точки гонки'),
                                          (a.race, a.base[1], 'r_c', 400, 'вспышка точки гонки')):
        n = bluer(Path(run) / f'{shot}.png', Path(base) / f'{shot}.png', (0, 40, 480, 250))
        print(f'  пиксели {what} ({shot}): голубее прежнего {n} (нужно > {need})')
        if n <= need: fails.append(f'{what}: на кадре {shot} нет нового голубого света ({n} пикс.)')
for f in fails: print('  FAIL', f)
print('RESULT', 'PASS' if not fails else f'FAIL {len(fails)}')
sys.exit(1 if fails else 0)
