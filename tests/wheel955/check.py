#!/usr/bin/env python3
# №955б: у машины миссии/угнанной под игроком колёса крутятся. Строки OWNANG (flag carang): угол качения spin2 за 5 с езды и скорость.
#   check.py smoke.txt -> «ход угла N рад при средней скорости V; растёт ли», последняя строка OK/BAD. OK: |Δугла| ≥ 20 рад при скорости > 5 м/с и forced != «-»
import re, sys
rows = []
for l in open(sys.argv[1], errors='replace'):
    m = re.match(r'OWNANG t=([\d.]+) onfoot=(\d) v=(-?[\d.]+) spin2=(-?[\d.]+) forced=(\S+)', l)
    if m and m.group(2) == '0' and m.group(5) != '-': rows.append((float(m.group(1)), float(m.group(3)), float(m.group(4))))
if len(rows) < 6: print('мало строк OWNANG с машиной под игроком: %d' % len(rows)); print('BAD'); sys.exit(1)
# угол крутится по модулю 2π·64 (402 рад): разворачиваем
tot = 0.0
for (t0, v0, a0), (t1, v1, a1) in zip(rows, rows[1:]):
    d = a1 - a0
    if d < -200: d += 402.12
    tot += d
vs = [v for _, v, _ in rows]; mv = sum(vs) / len(vs)
print('замер: за %.1f с средняя скорость %.1f м/с, угол качения колеса сдвинулся на %.1f рад' % (rows[-1][0] - rows[0][0], mv, tot))
ok = mv > 5 and abs(tot) >= 20
print('OK' if ok else 'BAD'); sys.exit(0 if ok else 1)
