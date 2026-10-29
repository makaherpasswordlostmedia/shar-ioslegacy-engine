#!/usr/bin/env python3
"""Гейт финального тура по худшим точкам (tests/me/psp_tour_final_points.txt, psp_tour_final_bonus.txt).
Использование: tools/tour_final_gate.py build/psp-tour/<папка с smoke.txt> [ещё папки]
Точка проходит, если: STAT-строка точки есть, пропусков (missed) 0, p95 <= 31 мс, строка миссии MSN mainat совпала
с ожидаемой (id и этап), и в smoke.txt есть строка причины ближней плоскости для сцены (NEARWHY, см. ниже).
Причина ближней плоскости: поле near_why= в строках PHSUB (Трассы 24f922c4, влито в build31) или строка NEARWHY;
без них гейт пишет «нет лога» и не засчитывает точку.
Запуск туров и PSP этот скрипт не трогает: только читает готовые отчёты."""
import re, sys
from pathlib import Path
EXPECT = {  # сцена -> (id миссии, этап) из tests/me/psp_tour_final_points.txt
 'P3_sr3': ('sr3', 1), 'P4_m1e5': ('m1', 5), 'P5_m6e2': ('m6', 2), 'P5_m6e4': ('m6', 4), 'P5_m1e2': ('m1', 2),
 'P6_bm1e5': ('bm1', 5), 'P6_m2e1': ('m2', 1), 'P6_m7e1': ('m7', 1), 'B02': None, 'B05': None}
P95_MAX = 31.0
def main(dirs):
    bad = 0
    for d in dirs:
        f = Path(d) / 'smoke.txt'
        if not f.exists(): print(f'нет {f}'); bad += 1; continue
        stat, msn, near, cur = {}, {}, set(), None
        for ln in f.read_text(errors='replace').splitlines():
            m = re.match(r'SCENE (\S+)', ln)
            if m: cur = m.group(1)
            m = re.match(r'STAT (\S+) frames (\d+) p95 ([\d.]+) p99 ([\d.]+) max ([\d.]+) per \d+ missed (\d+)', ln)
            if m: stat[m.group(1)] = (int(m.group(2)), float(m.group(3)), float(m.group(5)), int(m.group(6)))
            m = re.match(r'MSN mainat (\S+) stage=(\d+)', ln)
            if m and cur: msn[cur] = (m.group(1), int(m.group(2)))
            if ('NEARWHY' in ln or (ln.startswith('PHSUB') and 'near_why=' in ln)) and cur: near.add(cur)   # PHSUB near_why= (Трассы 24f922c4)
        print(f'== {d}')
        for ln in f.read_text(errors='replace').splitlines():
            if ln.startswith('SHOTFILE') and 'clearchk=1' in ln: print('  щели:', ln[:120])   # хвост C_*: скорость не считается
        for sc, exp in EXPECT.items():
            if sc not in stat: continue
            n, p95, mx, miss = stat[sc]; why = []
            if miss: why.append(f'пропущено {miss}')
            if p95 > P95_MAX: why.append(f'p95 {p95:.2f} > {P95_MAX}')
            if exp and msn.get(sc) != exp: why.append(f'миссия {msn.get(sc)} вместо {exp}: индекс сдвинулся')
            if sc not in near: why.append('нет лога причины ближней плоскости')
            ok = not why; bad += not ok
            print(f'  {sc:10s} кадров {n:5d} p95 {p95:6.2f} max {mx:6.1f} пропусков {miss:3d}  {"ПРОШЛА" if ok else "НЕТ: " + "; ".join(why)}')
    return 1 if bad else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else print(__doc__) or 2)
