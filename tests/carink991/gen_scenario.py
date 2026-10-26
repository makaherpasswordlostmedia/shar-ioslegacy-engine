#!/usr/bin/env python3
# №991: сценарий приёмки. gen_scenario.py green|red > scenario.txt
# L1, трафик: первая машина встаёт, глаз вокруг неё (flag trfgo УГОЛ РАССТОЯНИЕ, flag trfgoh ВЫСОТА). На каждом ракурсе два кадра с одного места:
#   o — flag carink991 0 (прежнее), n — flag carink991 1 (новое; в красном сценарии тоже 0)
import sys
mode = sys.argv[1] if len(sys.argv) == 2 else "green"
newv = 1 if mode == "green" else 0
VIEWS = [(20, 8.0, 0.0), (20, 8.0, 3.14), (26, 10.4, 0.0), (11, 3.4, 0.0), (8, 2.6, 0.0)]   # расстояние, высота глаза (м), угол (рад): три четверти сверху и с торца
L = ["wait 12", "flag cfgdefaults 1", "flag repair", "wait 4", "flag toon 1", "wait 4", "flag flat912 1", "scene G_ON", "foot 295.5 166 3.14", "wait 22", "flag trfgo 0.0", "wait 2"]
for i, (d, h, a) in enumerate(VIEWS):
    L += [f"flag trfgoh {h}", f"flag trfgo {a} {d}", "flag carink991 0", "wait 1.2", f"shot o{i}", f"flag carink991 {newv}", "wait 0.5", f"shot n{i}", "flag carink991 1"]
L += ["flag eyeon 0", "wait 1"]
print("\n".join(L))
