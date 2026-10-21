#!/usr/bin/env python3
"""Сверка прогона tests/ui/levelstats_scenario.txt: LEVEL PROGRESS паузы и экран конца уровня (LevelStats.pag).
  levelstats_check.py RUN_DIR   -> первая строка итог, код 0 = OK
Ожидания — с диска Роба, независимо от движка:
  · всего: сюжетных, бонусных миссий и уличных гонок уровня 1 — по флагам миссий пакета (tools/missions/compile.py, как
    MISSION SELECT), машин и одежды — строки BindReward уровня 1 (rewards.mfk), гэгов — SetTotalGags(1, N), карточек — 7
  · в паузе (LEVELSTATS pause): машин и одежды открыто по одной (своя по умолчанию), сюжет сделано < всего
  · после «все сюжетные миссии пройдены»: экран конца уровня (LEVELSTATS end, сюжет сделано = всего), X — дальше
    (MSN level-end-accept, потом LEVELDONE); «flag uilevelendold» (прежняя вспышка 3 с) — красный
  · процент — правило порта: всё сделанное / всё по восьми строкам (как viewer/ui.c uiLevelStatsPct)"""
import importlib.util, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
GAME = ROOT / 'hit-and-run-web/source/game'

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
kv = lambda l: dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
bad, info = [], []
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
c = mc.Compiler(1); c.compile(); P = c.pack
BONUS, SR, BM, NOSCRIPT, TRANS = 1, 2, 8, 16, 256
flags = [m[3] for m in P.missions]
want = dict(story=sum(1 for f in flags if not f & (BONUS | NOSCRIPT | TRANS)), races=sum(1 for f in flags if f & SR),
            bonus=sum(1 for f in flags if f & BM and not f & SR))
rw = (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace')
rew = re.findall(r'BindReward\(\s*"[^"]*",\s*"[^"]*",\s*"(car|skin)",\s*"[^"]*",\s*1\s*[,)]', rw)
want['cars'] = rew.count('car'); want['skins'] = rew.count('skin')
want['gags'] = int(re.search(r'SetTotalGags\(\s*1\s*,\s*(\d+)', rw).group(1)); want['cards'] = 7
info.append('с диска: ' + ', '.join(f'{k} {v}' for k, v in want.items()))
def stats(d): return {k: tuple(map(int, d[k].split('/'))) for k in ('gags', 'wasps', 'cars', 'skins', 'cards', 'races', 'bonus', 'story')}
lp = [kv(l) for l in log if l.startswith('LEVELSTATS pause')]; le = [kv(l) for l in log if l.startswith('LEVELSTATS end')]
if not lp: bad.append('LEVEL PROGRESS не открылся (нет LEVELSTATS pause)')
else:
    st = stats(lp[0]); info.append('пауза: ' + lp[0].get('pct', '?') + '% ' + ', '.join(f'{k} {a}/{b}' for k, (a, b) in st.items()))
    for k, v in want.items():
        if st[k][1] != v: bad.append(f'{k}: всего {st[k][1]}, на диске {v}')
    if st['cars'][0] != 1 or st['skins'][0] != 1: bad.append(f"открыто машин {st['cars'][0]}, одежды {st['skins'][0]} (ждём 1 и 1 — свои по умолчанию)")
    if st['story'][0] >= st['story'][1]: bad.append('в паузе сюжет уже пройден целиком?')
    tot = sum(b for a, b in st.values() if b > 0); dn = sum(min(a, b) for a, b in st.values() if b > 0)
    if int(lp[0]['pct']) != (dn * 100 + tot // 2) // tot: bad.append(f"процент {lp[0]['pct']} != {dn}/{tot}")
if not le: bad.append('экрана конца уровня не было (нет LEVELSTATS end)')
else:
    st = stats(le[0]); info.append('конец уровня: ' + le[0].get('pct', '?') + '% сюжет ' + '/'.join(map(str, st['story'])))
    if st['story'][0] != st['story'][1]: bad.append(f"конец уровня: сюжет {st['story']} не весь")
ia = next((i for i, l in enumerate(log) if l.startswith('MSN level-end-accept')), None)
ie = next((i for i, l in enumerate(log) if l.startswith('LEVELSTATS end')), None)
ix = next((i for i, l in enumerate(log) if l.startswith('PRESS cross') and ie is not None and i > ie), None)
idn = next((i for i, l in enumerate(log) if l.startswith('LEVELDONE')), None)
if ia is None or ix is None or ia < ix: bad.append('X на экране конца уровня не принят (нет MSN level-end-accept после нажатия)')
if idn is None or (ia is not None and idn < ia): bad.append('после X нет LEVELDONE')
for s in ('ls_pause', 'ls_end'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
print('levelstats: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)
