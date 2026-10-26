#!/usr/bin/env python3
# №990: сценарии. stills.txt — места с фонарями (по таблице света уровней), одна и та же камера: pool990 0 (как TEST70) и 1 (новое), счёт POOL990 и снимки.
# defaults.txt — езда по всем уровням без единой строки flag pool990: проверяет то, что реально едет в игре (по умолчанию)
import re
S = [  # уровень, имя, место (foot x z), камера: x y z, направление
 (1, 'l1', (-61.9, -301.0), (-49.9, 5.0, -301.0), (-1, -.3, 0)),
 (4, 'l4', (193.9, 107.3), (206.0, 11.0, 107.3), (-1, -.3, 0)),
 (5, 'l5b', (-517.9, -546.2), (-505.0, 28.5, -546.2), (-1, -.3, 0)),   # мост (признак №935: эллипса не было и раньше)
 (5, 'l5s', (-357.5, -156.8), (-345.5, 13.5, -156.8), (-1, -.3, 0)),   # уличный фонарь L5
 (6, 'l6p', (-396.1, -53.0), (-384.0, -63.0, -53.0), (-1, -.3, 0)),
 (7, 'l7n', (5.8, -260.9), (18.0, 7.0, -260.9), (-1, -.3, 0)),
 (3, 'l3', (-297.2, -172.2), (-285.0, -44.0, -172.2), (-1, -.3, 0)),
]
o = ["# №990: места с фонарями, pool990 0 (TEST70) и 1 (новое) с той же камерой; счёт POOL990 за 3 с; снимки p990_<место>_off/on",
     "scene F_L1", "flag cfgdefaults 1", "flag repair", "wait 6"]
prev = 1
for L, n, (fx, fz), c, d in S:
    if L != prev:
        prev = L
        o += [f"scene P990_GO{L}", "press circle 0.3", "wait 0.5", "press circle 0.3", "wait 0.5", f"flag golevel {L}", "wait 40", "wait 3"]
    o += [f"scene P990_S_{n}", f"foot {fx} {fz} 0", "wait 8", f"cam {c[0]} {c[1]} {c[2]} {d[0]} {d[1]} {d[2]} 70", "wait 2"]
    for on, tag in ((0, 'off'), (1, 'on')):
        o += [f"flag pool990 {on}", "wait 3", "flag pool990stat", f"shot p990_{n}_{tag}"]
    o += ["cam off", "wait 1"]
o.append("end")
open('stills.txt', 'w').write("\n".join(o) + "\n")
d = [l for l in open('lamps.txt').read().split("\n") if not re.match(r'flag pool990 [01]$', l)]
open('defaults.txt', 'w').write("\n".join(d))
