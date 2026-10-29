#!/usr/bin/env python3
# №993: значок дома №623 в углу вне задания. Читает MSNICON из smoke.txt (flag msnhud): want — какой значок просит этап, home — рисуется ли синтетический дом.
#   python3 check.py ok|bad|legit smoke.txt
#   ok    — ни одной строки, где дом стоит, а этап просит не «simpsons» (нужно хотя бы 3 строки, иначе пусто = ничего не доказано)
#   bad   — красный контроль: такая строка есть
#   legit — этап «simpsons» (L1 m1) по-прежнему рисует дом обычным значком задания: want=simpsons, field>=0, pix=1
import re, sys
mode, path = sys.argv[1], sys.argv[2]
rows = []
for l in open(path, errors='replace'):
    m = re.match(r'MSNICON want="([^"]*)" field=(-?\d+) pix=(\d+) pixok=(-?\d+) home=(\d+) ', l)
    if m: rows.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))))
if len(rows) < 3: print('мало строк MSNICON (%d): прогон не дошёл до игры' % len(rows)); sys.exit(2)
bad = [r for r in rows if r[4] and r[0] != 'simpsons']
stale = [r for r in rows if r[2] and r[3] == 0]
print('строк MSNICON %d, дом без этапа «simpsons»: %d, чужие пиксели у значка: %d' % (len(rows), len(bad), len(stale)))
if mode == 'ok': sys.exit(0 if not bad and not stale else 1)
if mode == 'bad': sys.exit(0 if bad else 1)
if mode == 'legit':
    n = [r for r in rows if r[0] == 'simpsons' and r[1] >= 0 and r[2]]
    print('этап simpsons рисует значок задания: %d строк' % len(n)); sys.exit(0 if n and not bad else 1)
