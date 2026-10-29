# №666/№667: сценарии «герой уровня садится в свою машину»: python3 -I tests/seat/gen.py ВЫХОД_ПАПКА
# Машина уровня стоит на старте (GAME car=x,z из журнала); герой телепортом у борта (+2,6 м по x), △, ждём посадку, SEAT-замер.
import sys, os
CARS = {1: (215.10, 170.31), 2: (152.00, -38.43), 3: (-3.35, -5.57), 4: (214.88, 172.27),
        5: (-154.90, -482.04), 6: (-300.14, -218.57), 7: (214.73, 172.41)}
OFF = {5: -2.6}   # L5: рядом стоит чужая votetruc — со стороны x+ она ближе своей apu_v
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for grp, name in (((1, 2, 3, 4), 'a'), ((5, 6, 7), 'b')):
    L = [f"# №666/№667: герои уровней {grp} в своих машинах (SEAT замер)"]
    for n in grp:
        x, z = CARS[n]
        L += [f"scene S_L{n}_load", f"flag golevel {n}", "wait 16", f"scene S_L{n}_out", f"foot {x + OFF.get(n, 2.6):.2f} {z:.2f} 3.14",
              "wait 3", "press triangle", "wait 6", "flag seatlog 0", "wait 1"]
    L.append("end")
    open(os.path.join(out, f"seat_{name}.txt"), "w").write("\n".join(L) + "\n")
