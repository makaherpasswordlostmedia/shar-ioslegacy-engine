#!/usr/bin/env python3
"""Гейт №929: после правила tools/flat_list.py асфальт проезжей части и стены с рисунком остаются родными текстурами, однотонное — заливкой.
  tests/toon/flat929.py НАБОР      НАБОР — папка с level.shr (L1) и l2…l7/level.shr; список ожиданий — flat929_expect.txt (по подписи уровня)
Красный контроль: ASPH929_OLD=1 WALL929_OLD=1 (прежнее правило) — гейт должен упасть."""
import sys, re, os
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent.parent / 'tools'))
import flat_list as F
pk = Path(sys.argv[1]); exp = {}
for ln in (here / 'flat929_expect.txt').read_text(encoding='utf-8').splitlines():
    m = re.match(r'(\w{8}) (L\d) native: ([\d ]+) \| fill: ([\d ]+)$', ln.strip())
    if m: exp[m.group(1)] = (m.group(2), [int(x) for x in m.group(3).split()], [int(x) for x in m.group(4).split()])
files = [pk / 'level.shr'] + [pk / f'l{n}' / 'level.shr' for n in range(2, 8)]
seen = 0; bad = 0
for lv in files:
    if not lv.exists(): continue
    data, rows, sig = F.build(str(lv), str(lv.with_name('notoon.txt')))
    key = f'{sig:08x}'
    if key not in exp: continue
    name, nat, fill = exp[key]; seen += 1
    wrong_nat = [i for i in nat if i >= len(rows) or rows[i][0] != 0]; wrong_fill = [i for i in fill if i >= len(rows) or rows[i][0] != 1]
    print(f'{name} {key}: родные {len(nat) - len(wrong_nat)}/{len(nat)}, заливка {len(fill) - len(wrong_fill)}/{len(fill)}' + (f'  ОШИБКА: должны быть родными {wrong_nat}, заливкой {wrong_fill}' if wrong_nat or wrong_fill else ''))
    bad += len(wrong_nat) + len(wrong_fill)
if not seen: print('FAIL ни одного уровня из списка в наборе (подписи не совпали)'); sys.exit(2)
print('PASS' if not bad else 'FAIL'); sys.exit(0 if not bad else 1)
