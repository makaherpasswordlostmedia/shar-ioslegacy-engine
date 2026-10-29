#!/usr/bin/env python3
"""Гейт горизонта: прогон смоука с горизонтом считается действительным, только если движок его реально загрузил и нарисовал.
  horizon_gate.py ДИР_ПРОГОНА [--old]        ДИР_ПРОГОНА = build/smoke/<время>
  по умолчанию: в smoke.txt есть «HORIZON loaded» (файл horizon.shr найден и разобран) И строка «HORIZON cost» с frames>0 и avg_us>0 (лента нарисована)
  --levels 1,2,3: ещё и для каждого из этих уровней должна быть своя «HORIZON loaded level=N» (файл принят движком; 22.10 L2 и L5 молча не приняты из-за потолка вершин)
  --old: красный контроль HORIZON_OLD=1: «HORIZON loaded» и «cost» ОТСУТСТВУЮТ (функция не рисует вовсе)
Выход 0 = гейт пройден, 1 = FAIL с причиной одной строкой (22.10 ошибка: прогоны без horizon.shr шли молча и «проходили»)."""
import re, sys
from pathlib import Path


def main():
    args = sys.argv[1:]; need = []
    if '--levels' in args:
        i = args.index('--levels'); need = [int(x) for x in args[i + 1].split(',')]; del args[i:i + 2]
    a = [x for x in args if not x.startswith('--')]
    old = '--old' in args
    if not a: print('FAIL: нужен ДИР_ПРОГОНА'); return 1
    f = Path(a[0]) / 'smoke.txt'
    if not f.exists(): print('FAIL: нет', f); return 1
    t = f.read_text(errors='replace')
    loaded = len(re.findall(r'^HORIZON loaded ', t, re.M))
    costs = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'^HORIZON cost (?:level=\d+ )?avg_us=(\d+) max_us=\d+ frames=(\d+)', t, re.M)]
    cost_lv = {int(m.group(1)) for m in re.finditer(r'^HORIZON cost level=(\d+) ', t, re.M)}
    if old:
        if loaded or costs: print('FAIL: HORIZON_OLD=1, а горизонт загружен/нарисован (loaded=%d cost=%d)' % (loaded, len(costs))); return 1
        print('OK (красный контроль): горизонт не загружен и не рисуется'); return 0
    if not loaded: print('FAIL: горизонт не загружен (нет «HORIZON loaded» в smoke.txt: horizon.shr не попал в прогон?)'); return 1
    if not costs or not any(us > 0 and n > 0 for us, n in costs): print('FAIL: горизонт загружен, но не нарисован (нет строки «HORIZON cost» с кадрами)'); return 1
    nodraw = [n for n in need if n not in cost_lv]
    if need and nodraw: print('FAIL: лента не нарисована (нет «HORIZON cost level=N») для уровней %s' % nodraw); return 1
    miss = [n for n in need if not re.search(r'^HORIZON loaded level=%d ' % n, t, re.M)]
    if miss: print('FAIL: горизонт не загружен для уровней %s (файл не принят движком: формат или размер)' % miss); return 1
    print('OK: loaded=%d, строк cost=%d, avg_us %d..%d' % (loaded, len(costs), min(c[0] for c in costs), max(c[0] for c in costs))); return 0


if __name__ == '__main__':
    sys.exit(main())
