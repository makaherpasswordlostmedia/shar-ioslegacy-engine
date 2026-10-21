#!/usr/bin/env python3
"""Правка 368 (и механика 353): тангаж машины в момент посадки с трамплина против 12 посадок оригинала.

Эталон — строки «удар» docs/handoff/ДЕЛЕГАТ_2026-10-05/patches/agent353_new/tests/jumps/pitch_ps2.tsv (близнец PS2 05.10,
tools/twins/jumpref.py --pitch-out, 4 трамплина L1): секунды от кромки и тангаж перед ударом. Порт — трассы tests/jumps/twin.c
--trace DIR (тот же заезд, что у оригинала): посадка — первый кадр с опорой после отрыва за кромкой, тангаж — в кадре перед ним.
Сторона: «нос» (ниже −3°) или «нет». Проверка: сторона совпадает у MIN_SAME из 12 (оригинал садится носом вниз в 11 из 12).
  air_pitch_ps2.py TRACE_DIR [--min-same N]   -> строки по заездам, «PASS/FAIL same N/12», код 0/1
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / 'docs/handoff/ДЕЛЕГАТ_2026-10-05/patches/agent353_new/tests/jumps/pitch_ps2.tsv'
args = sys.argv[1:]
min_same = 9
if '--min-same' in args:
    i = args.index('--min-same'); min_same = int(args[i + 1]); del args[i:i + 2]
if not args:
    print(f'НЕТ ДАННЫХ: не указан каталог трасс; эталон: {REF}')
    sys.exit(2)
trace_dir = Path(args[0]).resolve()
if not REF.is_file():
    print(f'НЕТ ДАННЫХ: эталон PS2 не найден: {REF}')
    sys.exit(2)
ref = {}
for line in REF.read_text(encoding='utf-8').splitlines():
    p = line.split('\t')
    if p[0] == 'удар': ref[p[1]] = (float(p[2]), float(p[3]))
if len(ref) != 12:
    print(f'НЕТ ДАННЫХ: в эталоне {REF} найдено {len(ref)}/12 записей «удар»')
    sys.exit(2)
if not trace_dir.is_dir():
    print(f'НЕТ ДАННЫХ: каталог трасс не найден: {trace_dir}')
    sys.exit(2)
trace_files = sorted(trace_dir.glob('*.tsv'))
trace_ids = {f.stem for f in trace_files}
missing = sorted(set(ref) - trace_ids)
if missing:
    print(f'НЕТ ДАННЫХ: в {trace_dir} нет трасс PS2-проб: {", ".join(missing)}')
    sys.exit(2)
same = total = 0
for f in trace_files:
    rid = f.stem
    if rid not in ref: continue
    rows = [list(map(float, l.split('\t'))) for l in open(f) if l.strip()]
    lip = next((r[0] for r in rows if r[4] >= 0), None)
    air, imp, prev = False, None, None
    for r in rows:   # t x y z along v vy grounded pitch roll wheels
        if lip is None or r[0] < lip: prev = r; continue
        if r[7] == 0: air = True
        elif air: imp = prev; break
        prev = r
    total += 1
    if imp is None: print(f'{rid:10} нет посадки у порта'); continue
    ok = (imp[8] < -3) == (ref[rid][1] < -3); same += ok
    print(f'{rid:10} PS2 {ref[rid][0]:.2f} с {ref[rid][1]:+6.1f}° | порт {imp[0] - lip:.2f} с {imp[8]:+6.1f}° {"ok" if ok else "другая сторона"}')
if total != len(ref):
    print(f'НЕТ ДАННЫХ: сопоставлено {total}/{len(ref)} PS2-проб из {trace_dir}')
    sys.exit(2)
res = same >= min_same
print(f'{"PASS" if res else "FAIL"} same {same}/{total} (нужно ≥ {min_same})')
sys.exit(0 if res else 1)
