#!/usr/bin/env python3
"""№946: сценарий заездов по предметам PRP1 уровня N: по 2 экземпляра каждого типа (старт — из переписи census.c, курс, с которого модуль сбивает).
python3 gen_hits.py ЧИСЛО_УРОВНЯ P.txt > сценарий.txt   (P.txt — вывод census LEVEL.shr P). Между заездами flag repair: после разбития машина не мешает следующим."""
import sys, random
lv, pf = sys.argv[1], sys.argv[2]
by = {}
for l in open(pf):
    r = l.rstrip('\n').split('\t')
    if r[0] == 'ST': by.setdefault(r[7], []).append(r)
random.seed(946); out = [f'# №946: L{lv}, заезд машиной в лоб (flag autostraight) по 2 предметам каждого типа PRP1; PROPKICK / PROPSTAT — сбит ли предмет в игре', 'scene P_load', f'flag golevel {lv}', 'wait 20', 'flag cfgdefaults 1', 'flag repair', 'scene P_hits']
for t, L in sorted(by.items(), key=lambda kv: int(kv[0].split()[1])):
    for r in random.sample(L, min(2, len(L))):
        out += ['flag repair', f'goto {r[3]} {r[4]} {r[5]}', 'wait 2.5', 'flag autostraight 3.4', 'wait 3.4', f'flag propstat {r[1]}']
out += ['flag repair', 'wait 1', 'end']
print('\n'.join(out))
