#!/usr/bin/env python3
"""Гейт тура 13 (tests/me/psp_tour_13.txt): старт миссии и езда отдельно.
  tools/tour_gate13.py build/psp-tour/<папка> [ещё папки]
Сцены *_T — старт миссии целиком (brief + ✕ + переход): показываем кадры по строкам таблицы по секундам (учитываются и кадры «settling»):
  максимум кадра, секунд с кадром > 50 мс, пропуски в STAT. Порог: максимум кадра перехода <= 120 мс (одиночный рывок допустим, это загрузка),
  секунд с > 50 мс <= 2.
Сцены *_D, P*_/H_* без суффикса (езда): STAT: пропусков 0 и p95 <= 31 мс.
Счётчик щелей: строки SHOTFILE ... clearchk=1 (сцены C_*), скорость не считается."""
import re, sys
from pathlib import Path
ROW = re.compile(r'([\d.]+) (\S+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) (\d+) (\d+) ([\d.]+) (\S+) (\d+) (\d+) (\d+) (\d+) ([\d.]+)( settling)?')
STAT = re.compile(r'STAT (\S+) frames (\d+) p95 ([\d.]+) p99 ([\d.]+) max ([\d.]+) per \d+ missed (\d+)')
def main(dirs):
    bad = 0
    for d in dirs:
        f = Path(d) / 'smoke.txt'
        if not f.exists(): print(f'нет {f}'); bad += 1; continue
        rows, stat, shots = {}, {}, []
        for ln in f.read_text(errors='replace').splitlines():
            m = ROW.match(ln)
            if m: rows.setdefault(m.group(2), []).append((float(m.group(5)), int(m.group(11))))   # workmax, missed
            m = STAT.match(ln)
            if m: stat[m.group(1)] = (int(m.group(2)), float(m.group(3)), float(m.group(5)), int(m.group(6)))
            if ln.startswith('SHOTFILE') and 'clearchk=1' in ln: shots.append(ln[:130])
        print(f'== {d}')
        for sc in stat:
            if sc.endswith('_T'):
                R = rows.get(sc, [])[1:]   # первая строка сцены — кадр загрузки миссии (4,4-4,7 с на экране загрузки), в рывок не считается
                mx = max([w for w, _ in R], default=0); slow = sum(1 for w, _ in R if w > 50); ms = sum(m for _, m in R)
                ok = len(R) > 0 and mx <= 120 and slow <= 2; bad += not ok
                print(f'  {sc:16s} ПЕРЕХОД  макс кадр {mx:6.1f} мс, секунд >50 мс {slow}, пропусков {ms:3d}  {"ПРОШЛА" if ok else "НЕТ"}')
            elif sc.endswith('_D') or sc.startswith(('H_', 'P')) and not sc.endswith('_T'):
                n, p95, mx, miss = stat[sc]; ok = n > 0 and miss == 0 and p95 <= 31.0; bad += not ok
                print(f'  {sc:16s} ЕЗДА     кадров {n:4d} p95 {p95:6.2f} max {mx:6.1f} пропусков {miss:3d}  {"ПРОШЛА" if ok else "НЕТ"}')
        for s in shots: print('  щели:', s)
    return 1 if bad else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else print(__doc__) or 2)
