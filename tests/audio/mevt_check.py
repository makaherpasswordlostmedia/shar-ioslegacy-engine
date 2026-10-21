#!/usr/bin/env python3
"""Правка Роба 207 (03.10: «не начинается музыка уровня; когда начинается миссия, музыка меняется»): у каждого события старта
миссии уровня (M0_start..M7_start, Bonus_start) в таблице MEVT есть дорожки, и они те же, что даёт сама композиция диска
(tools/rms.py: событие -> play_region -> первые потоки). Красный: MEV_NAME_ORDER_ONLY=1 (прежний разбор по порядку строк) —
M0_start пустой.   python3 tests/audio/mevt_check.py [--level 1]"""
import argparse, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))
import sound_export as SE, rms as RMS
ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); a = ap.parse_args()
tracks, events, rep = SE.mission_music(a.level)
C = RMS.read(str(SE.SND / 'music' / f'l{a.level}_music.rms'))
names = {t[1]: t[0] for t in tracks}
bypath = {t[0]: Path(t[1]).stem.lower() for t in tracks}   # имя дорожки -> файл (имя дорожки бывает своё: m5_intro = Motown_Intro.rsd)
loops = {t[0]: t[2] for t in tracks}
fails = 0
for ev, ts, kind in events:
    if not ev.lower().endswith('_start'): continue
    acts = next((x for nm, x in C.events() if nm == ev), [])
    ri = next((r for kd, r in acts if kd == 'play_region' and r is not None), None)
    want = [C.stream_file(si)[1].lower().split('\\')[-1] for si in C.region_streams(ri)[0]] if ri is not None else []
    ok = bool(ts) and (not want or any(bypath.get(t, t) == w for t in ts for w in want))
    print(f"  {ev:14s} дорожки {', '.join(ts) if ts else '—':<40} композиция {want} {'ok' if ok else 'ПУСТО/НЕ ТО'}")
    fails += not ok
# правка 234: «пешком» — петля там, где регион композиции повторяется (M2/M3/M5/M6/M7), один проход у M0/M1
for ev, ts, kind in events:
    if not ev.lower().endswith('_get_out_of_car') or not ts: continue
    acts = next((x for nm, x in C.events() if nm == ev), [])
    ri = next((r for kd, r in acts if kd == 'play_region' and r is not None), None)
    want_loop = ri is not None and any(rp for rp, _ in C.region_plan(ri)); have = all(loops.get(t) for t in ts)
    print(f"  {ev:20s} петля {'да' if have else 'нет'} (композиция: {'да' if want_loop else 'нет'}) {'ok' if have == want_loop else 'НЕ ТАК'}")
    fails += have != want_loop
print('RESULT', 'FAIL' if fails else 'OK', f'({fails} несовпадений с композицией)')
sys.exit(1 if fails else 0)
