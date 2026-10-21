# №667 глобально: герой каждого уровня садится в СВОЮ машину и выходит (дверь, анимация, без ириса): python3 -I tests/seat/gen_own.py ПАПКА [знак стороны водителя: 1 или -1] [номера уровней через запятую]
# Камера снаружи со стороны водителя (локальный -x модели: мир (sgn*cos h, -sgn*sin h)), 7,5 м, смотрит на машину; по 2 кадра на уровень: дверь при посадке, дверь при выходе.
import sys, os, math
CARS = {1: (215.10, 3.50, 170.31, 1.571), 2: (152.00, 7.28, -38.43, 5.716), 3: (-3.35, 6.66, -5.57, 0.002), 4: (214.88, 3.37, 172.27, 3.322),
        5: (-154.90, 28.85, -482.04, 0.024), 6: (-300.14, -53.00, -218.57, 4.644), 7: (214.73, 3.37, 172.41, 3.142)}
HI = {5: 4.0}   # L5: чужая votetruc загораживает вид сбоку — камера выше
K = {1: -2.0, 5: 2.5}   # сдвиг героя вдоль машины: L1 у стены дома — с водительской стороны путь закрыт (ирис по правке 212), L5 рядом стоит чужая votetruc, ближе своей
ONLY = [int(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
out = sys.argv[1]; sg = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
os.makedirs(out, exist_ok=True)
for grp, name in (((1, 2, 3, 4), 'a'), ((5, 6, 7), 'b')):
    L = [f"# №667: герой уровней {grp} садится в свою машину и выходит"]
    for n in grp:
        if ONLY and n not in ONLY: continue
        x, y, z, h = CARS[n]; fx, fz = math.sin(h), math.cos(h); k = K.get(n, 0.0); dx, dz = sg * math.cos(h), -sg * math.sin(h)
        L += [f"scene O_L{n}_load", f"flag golevel {n}", "wait 16", f"scene O_L{n}",
              f"cam {x + 7.5 * dx:.2f} {y + 1.8 + HI.get(n, 0.0):.2f} {z + 7.5 * dz:.2f} {-7.5 * dx:.2f} {-0.15 - HI.get(n, 0.0) * 0.8:.2f} {-7.5 * dz:.2f} 40",
              f"foot {x + 2.4 * dx + k * fx:.2f} {z + 2.4 * dz + k * fz:.2f} 0", "wait 3", "press triangle", "wait 0.6", f"shot O_L{n}_in", "wait 4.5",
              "flag seatlog 0", "press triangle", "wait 0.5", f"shot O_L{n}_out", "wait 2"]
    L.append("end")
    open(os.path.join(out, f"own_{name}.txt"), "w").write("\n".join(L) + "\n")
