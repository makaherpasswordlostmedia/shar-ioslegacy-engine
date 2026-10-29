#!/usr/bin/env python3
"""Аудит 09.10 п. 20: водители машин миссий (tests/missions/drivers.sh).
   drivers_check.py ПРОГОН ЭТАЛОН_БЕЗ_ВОДИТЕЛЕЙ
Проверки: в сценах sr2, m7, m6 «MSN drivers-drawn» ≥ 1; на снимках sr2_back (Барт в honor_v) и m7_front (Смитерс в smith_v) в рамке
машины миссии ≥ 12 пикселей отличаются от снимка сборки без водителей (-DMV_DRIVERS_OLD=1) — голова и плечи над бортом/за стеклом.
Красный контроль: тот же скрипт на паре (без водителей, без водителей) обязан упасть."""
import sys, re
from pathlib import Path
import numpy as np
from PIL import Image
run, ref = Path(sys.argv[1]), Path(sys.argv[2])
BOX = {'sr2_back': (290, 100, 340, 140), 'm7_front': (255, 90, 310, 135)}   # рамка машины миссии на снимке 480x272 (сценарий: goto)
NEED_PX = 12
fails = 0
def check(name, ok, d):
    global fails
    print(f'CHECK {name:10s} {"OK  " if ok else "FAIL"}  {d}'); fails += not ok
def drawn(r):   # наибольшее «MSN drivers-drawn N» внутри каждой сцены
    out, sc = {}, None
    for ln in (r / 'smoke.txt').read_text(errors='replace').splitlines():
        m = re.match(r'SCENE (\S+)', ln)
        if m: sc = m.group(1); out.setdefault(sc, 0); continue
        m = re.match(r'MSN drivers-drawn (\d+)', ln)
        if m and sc: out[sc] = max(out[sc], int(m.group(1)))
    return out
dn = drawn(run)
for sc in ('sr2', 'm7', 'm6'):
    check(f'drawn_{sc}', dn.get(sc, 0) >= 1, f'водителей в кадре в сцене {sc}: {dn.get(sc, 0)} (нужно ≥ 1)')
for shot, (x0, y0, x1, y1) in BOX.items():
    a = np.asarray(Image.open(run / f'{shot}.png').convert('RGB'), np.int16)
    b = np.asarray(Image.open(ref / f'{shot}.png').convert('RGB'), np.int16)
    d = np.abs(a - b).sum(2) > 60
    inb = int(d[y0:y1, x0:x1].sum())
    check(shot, inb >= NEED_PX, f'пикселей водителя в рамке машины {inb} (нужно ≥ {NEED_PX}), вне рамки {int(d.sum()) - inb}')
print(f'RESULT {"FAIL" if fails else "PASS"} провалов {fails}')
sys.exit(1 if fails else 0)
