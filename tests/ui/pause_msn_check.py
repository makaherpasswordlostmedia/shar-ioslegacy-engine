#!/usr/bin/env python3
"""Сверка прогона tests/ui/pause_msn_scenario.txt: пауза миссии PauseMission.scr (viewer/ui.c uiPauseMission, main.c).
  pause_msn_check.py RUN_DIR   -> первая строка итог, код 0 = OK
  · в основной части миссии m0 START открывает паузу миссии (PAUSE on mission=1), пунктов в пакете — строки PauseMission.pag
    по порядку (CONTINUE, RESTART MISSION, CANCEL MISSION, OPTIONS, QUIT GAME — tools/ui_export.py pausemsn)
  · RESTART MISSION: миссия заново (MSN pause-restart m0), после неё снова пауза миссии
  · CANCEL MISSION: отмена (MSN pause-abort m0), после неё START — пауза свободной езды (PAUSE on mission=0)
  · снимки обеих пауз есть; «flag pauseold» (прежний код: в миссии пауза свободной езды) — красный"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
bad, info = [], []
ev = [l for l in log if l.startswith('PAUSE on ') or l.startswith('MSN pause-') or l.startswith('MSN mission ')]
info.append(' | '.join(' '.join(l.split()[:3]) for l in ev))
seq = [('P1' if 'mission=1' in l else 'P0') if l.startswith('PAUSE') else ('R' if 'pause-restart' in l else 'A' if 'pause-abort' in l else None)
       for l in ev]
seq = [x for x in seq if x]
want = ['P1', 'R', 'P1', 'A', 'P0']
if seq[:5] != want: bad.append(f'порядок {seq} != {want} (пауза миссии -> RESTART -> пауза миссии -> CANCEL -> пауза свободной езды)')
import ui_export as U
items, _ = U.build_items('pausemsn')
names = [it['name'] for it in sorted((i for i in items if i['page'] == 'PauseMission.pag' and i['menu'] >= 0), key=lambda t: t['menu'])]
if names != ['Continue', 'RestartMission', 'AbortMission', 'Options', 'QuitGame']: bad.append(f'пункты паузы миссии в пакете: {names}')
info.append('пункты: ' + ', '.join(names))
for s in ('pause_msn', 'pause_free'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
if not any(l.startswith('END') for l in log): bad.append('нет END')
print('pause mission: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)
