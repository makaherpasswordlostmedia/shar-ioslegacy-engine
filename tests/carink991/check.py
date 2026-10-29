#!/usr/bin/env python3
# №991: сверка кадров приёмки. check.py ПАПКА_out [--min-freed N] — печатает по ракурсам и итог; код 0 — годится
#   freed  — пикселей, которые были тёмной тушью в o (прежнее) и стали светлыми в n (новое): крыша и бока, которые перестала красить оболочка
#   gained — наоборот (новое темнее прежнего): шум и сдвиг линии, не больше половины freed
#   keep   — тёмных пикселей в n не меньше 60 % от o: контур остался (кроме закрашенной крыши, прежнее и новое отличаются на доли)
import sys, numpy as np
from PIL import Image
d = sys.argv[1]; need = int(sys.argv[sys.argv.index("--min-freed") + 1]) if "--min-freed" in sys.argv else 150
box = (180, 80, 300, 180)   # центр кадра: глаз смотрит на машину
def lum(n): return np.asarray(Image.open(f"{d}/{n}.png").convert("RGB").crop(box)).astype(int).sum(2) / 3
good = 0; bad = 0
for i in range(5):
    o, n = lum(f"o{i}") < 80, lum(f"n{i}") < 80
    freed, gained = int((o & ~n).sum()), int((~o & n).sum()); keep = int(n.sum()) / max(1, int(o.sum()))
    hit = freed >= need and gained <= freed // 2 + 40 and keep >= .6
    print(f"  ракурс {i}: освобождено {freed}, добавилось {gained}, осталось тёмного {keep:.0%}  {'ok' if hit else 'мало/не так'}")
    good += hit
print(f"годных ракурсов {good} из 5 (нужно 4)")
sys.exit(0 if good >= 4 else 1)
