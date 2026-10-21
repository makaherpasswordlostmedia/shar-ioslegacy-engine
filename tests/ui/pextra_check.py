#!/usr/bin/env python3
"""Сверка прогона tests/ui/pextra_scenario.txt: VIEW CARDS (PauseViewCards.scr) и MISSION SELECT (MissionSelect.scr), pextra.shr.
  pextra_check.py RUN_DIR   -> первая строка итог, код 0 = OK
  · VIEW CARDS открылся с маской собранных 5 (карточки 1 и 3), X на карточке 1 — крупно, X — обратно, на несобранной (2) X не
    открывает, △ — закрыт
  · MISSION SELECT — экран оригинала (MSNSEL open rows=1, 7 строк), курсор на текущей m3 (строка 2), ↑ + X — запущена m2
  · строки MissionSelect.pag в пакете = 7 последних сюжетных миссий уровня 1 по данным миссий (tools/missions/compile.py)
  · снимки есть; без pextra.shr в наборе — красный (VIEW CARDS выключен, MISSION SELECT — прежний список)"""
import importlib.util, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
kv = lambda l: dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
bad, info = [], []
vc = [(l.split()[1], kv(l)) for l in log if l.startswith('VIEWCARDS ')]
info.append('VIEW CARDS: ' + ' '.join(f"{e}:{d.get('sel')}" for e, d in vc))
ev = [e for e, _ in vc]
if not vc or vc[0][0] != 'open' or vc[0][1].get('got') != '5': bad.append(f'VIEW CARDS не открылся с маской 5: {vc[:1]}')
if ('zoom', '0') not in [(e, d.get('sel')) for e, d in vc]: bad.append('X на собранной карточке 1 не открыл её крупно')
if any(e == 'zoom' and d.get('sel') == '1' for e, d in vc): bad.append('несобранная карточка 2 открылась крупно')
if 'close' not in ev: bad.append('VIEW CARDS не закрылся по △')
ms = [kv(l) for l in log if l.startswith('MSNSEL open')]
if not ms or ms[0].get('rows') != '1' or ms[0].get('n') != '7' or ms[0].get('sel') != '2':
    bad.append(f'MISSION SELECT не экран оригинала на текущей m3: {ms[:1]}')
else: info.append('MISSION SELECT: ' + ' '.join(f'{k}={v}' for k, v in ms[0].items()))
if not any(l.startswith('MSN select m2') for l in log): bad.append('↑ + X не запустил m2')
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
c = mc.Compiler(1); c.compile(); P = c.pack
story = [P.strings[m[1]] for m in P.missions if not m[3] & (1 | 16 | 256)]
import ui_export as U
its, _ = U.build_items('missionselect')
rows = [it['strings'][0] for it in sorted((i for i in its if i['page'] == 'MissionSelect.pag' and i['type'] == U.T_TEXT and i['menu'] >= 0),
                                          key=lambda t: t['menu'])]
if rows != story[-7:]: bad.append(f'строки пакета {rows} != 7 последних сюжетных {story[-7:]}')
for s in ('vc_grid', 'vc_zoom', 'ms_list'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
print('pause extra: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)
