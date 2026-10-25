#!/usr/bin/env python3
"""Гейт №932б: tests/zf932/gate.py БАЗА_L3 БАЗА_L5 НОВОЕ_L3 НОВОЕ_L5  (smoke.txt прогонов tests/zf932/flick_l3.txt и flick_l5.txt прежней сборкой и новой; пары сцен FK_L3_STREET/PIER, FK_L5_CENTRE/BRIDGE)
Проверки (far% — мерцающая площадь кадра дальше 60 м и «без глубины», tests/zf932/flick_table.py; b0 — полоса ближе 30 м):
  1) эстакада L5 (FK_L5_BRIDGE): far% новой не больше 0,75 прежней (минус 25 %);  2) набережная L3 (FK_L3_PIER): не больше 0,92 прежней;
  3) ни одна из четырёх сцен не стала хуже больше чем на 8 % (far%) и ближняя полоса b0 не хуже больше чем на 10 %;  4) в новой сборке есть строки ZF932 (дальний проход был), в прежней нет;
  5) оба прогона дошли до END.  Код 0 — PASS."""
import re, sys, subprocess
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
def load(p):
    txt = Path(p).read_text(errors='replace')
    out = subprocess.run([sys.executable, str(here / 'flick_table.py'), '--json', p], capture_output=True, text=True).stdout
    import json
    return {json.loads(l)['scene']: json.loads(l) for l in out.splitlines() if l.strip()}, txt
bl3, tb3 = load(sys.argv[1]); bl5, tb5 = load(sys.argv[2]); nl3, tn3 = load(sys.argv[3]); nl5, tn5 = load(sys.argv[4])
base = {**bl3, **bl5}; new = {**nl3, **nl5}; bad = []
for t in (tb3, tb5, tn3, tn5):
    if 'END' not in t.split(): bad.append('прогон не дошёл до END')
if 'ZF932 ' not in tn3 or 'ZF932 ' not in tn5: bad.append('в новой сборке нет строк ZF932: дальний проход не включался')
if 'ZF932 ' in tb3 or 'ZF932 ' in tb5: bad.append('в прежней сборке есть ZF932: она не прежняя')
for sc in ('FK_L3_STREET', 'FK_L3_PIER', 'FK_L5_CENTRE', 'FK_L5_BRIDGE'):
    if sc not in base or sc not in new: bad.append(f'нет сцены {sc}'); continue
    b, n = base[sc], new[sc]; r = n['far'] / b['far'] if b['far'] else 1.0; r0 = n['b0'] / b['b0'] if b['b0'] else 1.0
    print(f'{sc}: far% {b["far"]:.4f} -> {n["far"]:.4f} (x{r:.2f}), b0 {b["b0"]:.4f} -> {n["b0"]:.4f} (x{r0:.2f})')
    if r > 1.08: bad.append(f'{sc}: far% хуже на {100 * (r - 1):.0f} %')
    if r0 > 1.10: bad.append(f'{sc}: ближняя полоса хуже на {100 * (r0 - 1):.0f} %')
    if sc == 'FK_L5_BRIDGE' and r > 0.75: bad.append(f'эстакада L5: far% только x{r:.2f} (нужно ≤ 0,75)')
    if sc == 'FK_L3_PIER' and r > 0.92: bad.append(f'набережная L3: far% только x{r:.2f} (нужно ≤ 0,92)')
for x in bad: print('FAIL', x)
print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
