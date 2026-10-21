# №314 п.1: водители машин миссий — по каждой миссии уровня: старт, игрок в 6 м сбоку от первой машины с водителем (flag msncarnear), снимок. python3 -I tests/seat/gen_drv.py ПАПКА
import sys, os
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for n in range(1, 7):
    L = [f"# №314 п.1: водители машин миссий L{n}", f"scene D{n}_load", f"flag golevel {n}", "wait 16", "flag msn", "wait 3"]
    for k in range(13):
        L += [f"scene D{n}_k{k}", f"flag msnmain {k}", "wait 3.5", "press cross", "wait 0.8", "flag msncarnear 0", "wait 1.7", f"shot D{n}_k{k}"]
    L.append("end")
    open(os.path.join(out, f"d{n}.txt"), "w").write("\n".join(L) + "\n")
