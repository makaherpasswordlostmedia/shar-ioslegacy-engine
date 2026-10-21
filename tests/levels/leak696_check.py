#!/usr/bin/env python3
"""Сверка гейта №696 (tests/levels/leak696.sh) по smoke.txt цепочки 1..7,1..7,1.
Строки LEVEL ev=load: heap0 = свободная куча перед загрузкой уровня (после выгрузки прежнего), mx0 = крупнейший блок в тот же момент.
Условия (МБ): 1) куча перед загрузкой того же уровня в следующем круге не ниже прежней круга больше чем на 0,2; 2) вся цепочка: heap0 не ниже
первого замера (L2) больше чем на 1,0 (разброс от разных пакетов игрока и звука уровня); 3) mx0 в кругах 2 и 3 не ниже минимума круга 1 больше чем на 0,2;
4) каждый L7: col=1 traffic=1; 5) allocfail (столбец 14 строк по секундам) = 0 всегда; 6) 15 загрузок. Код 0 = OK"""
import re, sys
def kv(l): return dict(re.findall(r'(\w+)=(\S+)', l))
log = open(sys.argv[1], errors='replace').read().splitlines()
loads = [kv(l) for l in log if l.startswith('LEVEL ') and ' ev=load ' in l]
bad = []; MB = 1048576.0
if len(loads) < 15: bad.append('загрузок %d из 15' % len(loads))
rows = [(int(d['n']), int(d['heap0']) / MB, int(d['mx0']) / MB, d) for d in loads]
r1, r2, r3 = rows[1:7], rows[8:14], rows[14:15]   # круг 1: L2..L7 (L1 — старт, свободно меньше: первая загрузка до меню), круг 2: L2..L7, затем L1
first = rows[1][1] if len(rows) > 1 else 0
for a, b in zip(rows[1:7], rows[8:14]):
    if a[1] - b[1] > 0.2: bad.append('куча перед L%d: круг 1 %.2f, круг 2 %.2f (минус %.2f МБ)' % (a[0], a[1], b[1], a[1] - b[1]))
if len(rows) >= 16 and rows[7][1] - rows[14][1] > 0.2: bad.append('куча перед L1: %.2f -> %.2f' % (rows[7][1], rows[14][1]))
for n, h, m, d in rows[1:]:
    if first - h > 1.0: bad.append('куча перед L%d %.2f МБ: ниже первого замера %.2f больше чем на 1,0' % (n, h, first))
mn = min(m for n, h, m, d in r1) if r1 else 0
for n, h, m, d in rows[8:]:
    if mn - m > 0.2: bad.append('крупнейший блок перед L%d %.2f МБ: ниже минимума круга 1 (%.2f)' % (n, m, mn))
for n, h, m, d in rows:
    if n == 7 and (d.get('col') != '1' or d.get('traffic') != '1'): bad.append('L7: col=%s traffic=%s' % (d.get('col'), d.get('traffic')))
af = [l.split()[13] for l in log if re.match(r'^[0-9.]+ \S+ [0-9.]+ ', l) and len(l.split()) > 13]
if any(x not in ('0',) for x in af): bad.append('allocfail не 0: %s' % sorted(set(af)))
print('heap0 МБ: ' + ' '.join('L%d=%.2f' % (n, h) for n, h, m, d in rows))
print('mx0   МБ: ' + ' '.join('L%d=%.2f' % (n, m) for n, h, m, d in rows))
for b in bad: print('ПРОВАЛ: ' + b)
sys.exit(1 if bad else 0)
