#!/usr/bin/env python3
"""Сверка прогона tests/pause_rows/scenario.txt (правка Роба 137): строки паузы по логу PAUSEROWS / PAUSEACT (viewer/main.c).
  check.py RUN_DIR [--planted]   -> первая строка итог, код 0 = OK
  Без ключа: открытия паузы 1 и 3 (игрок) — без RESET CAR, ↓ + X в первом — не act=1; открытие 2 (flag resetrowold) и 4
  (служебный) — строка RESET CAR есть, в открытии 2 ↓ + X = act=1 (проверка видит строку, когда она есть).
  --planted (красный): к открытию 2 (прежний код) применяются требования игрока — обязано упасть."""
import sys
from pathlib import Path
run = Path(sys.argv[1]); planted = '--planted' in sys.argv
log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
opens = []                                     # [(строка PAUSEROWS, [act...])]
for l in log:
    if l.startswith('PAUSEROWS'): opens.append((l, []))
    elif l.startswith('PAUSEACT') and opens: opens[-1][1].append(int(l.split('act=')[1].split()[0]))
bad = []
if len(opens) < 4: bad.append(f'открытий паузы {len(opens)} < 4')
else:
    rc = lambda o: 'RESET CAR' in o[0]
    for i in ([0, 1, 2] if planted else [0, 2]):
        if rc(opens[i]): bad.append(f'открытие {i + 1} (игрок): есть RESET CAR')
        if 1 in opens[i][1]: bad.append(f'открытие {i + 1} (игрок): ↓ + X дал RESET CAR (act=1)')
    if not planted:
        if not rc(opens[1]) or 1 not in opens[1][1]: bad.append('открытие 2 (resetrowold): строки RESET CAR / act=1 нет — проверка слепая')
        if not rc(opens[3]): bad.append('открытие 4 (служебный): нет RESET CAR')
for s in ('pause_player', 'pause_old', 'pause_service'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
if not any(l.startswith('END') for l in log): bad.append('нет END')
print(('OK' if not bad else 'FAIL ' + '; '.join(bad)) + ' · pause_rows' + (' (planted)' if planted else ''))
for o in opens: print('  ' + o[0].strip() + '  act=' + ','.join(map(str, o[1])))
sys.exit(1 if bad else 0)
