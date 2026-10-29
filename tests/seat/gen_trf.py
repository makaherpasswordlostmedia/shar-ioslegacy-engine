# №666/№667: угон одной модели трафика на уровнях L2–L7 героем уровня: python3 -I tests/seat/gen_trf.py ПАПКА [heads.json]
# Без heads.json — проход 1 (SEAT headw, позиции); с ним — кадры сквозь лобовое стекло спереди (стекло полупрозрачное; боковые окна непрозрачные).
import sys, os, json
CARS = {2: (152.00, -38.43), 3: (-3.35, -5.57), 4: (214.88, 172.27), 5: (-154.90, -482.04), 6: (-300.14, -218.57), 7: (214.73, 172.41)}
MODEL = {2: 3, 3: 3, 4: 2, 5: 2, 6: 3, 7: 0}   # номер модели в пакете: pizza, fishtruc, garbage, ambul, IStruck, coffin
out = sys.argv[1]; heads = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
os.makedirs(out, exist_ok=True)
for grp, name in (((2, 3, 4), 'a'), ((5, 6, 7), 'b')):
    L = [f"# №666/№667: герой уровней {grp} угоняет машину трафика (trfspawn), сидит, выходит"]
    for n in grp:
        x, z = CARS[n]
        L += [f"scene T_L{n}_load", f"flag golevel {n}", "wait 16", "flag msn", "wait 3", f"scene T_L{n}", f"foot {x + 2.6:.2f} {z:.2f} 3.14", "wait 3",
              f"flag trfspawn {MODEL[n]}", "wait 0.3", "press triangle", "wait 4", "flag seatlog 0"]
        h = heads.get(str(n))
        if h:   # голова водителя в мире: камера 2,8 м впереди машины (курс π: нос в -z), смотрит на неё сквозь лобовое; потом чуть сбоку
            hx, hy, hz = h
            L += [f"cam {hx + 0.4:.2f} {hy + .35:.2f} {hz - 2.8:.2f} -0.1 -0.12 1 45", "wait 1", f"shot T_L{n}_side",
                  f"cam {hx - 1.3:.2f} {hy + .45:.2f} {hz - 2.4:.2f} 0.55 -0.15 1 45", "wait 1", f"shot T_L{n}_34"]
        L += ["wait 1"]
    L.append("end")
    open(os.path.join(out, f"trf_{name}.txt"), "w").write("\n".join(L) + "\n")
