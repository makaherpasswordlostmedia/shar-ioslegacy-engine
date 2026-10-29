#!/usr/bin/env python3
# №944 гейт формы звезды входа по растру эмулятора: снимок листа (flag glintlab 2, tests/glint944/lab2.txt): одна звезда входа через настоящий путь рисования msnart.c,
# центр (240, 116), полуось квада 38,4 пикс, кончик большого луча 48. Мерим по картинке, не по коду:
#   четыре луча большой звезды A на своих углах и длинах (.80 / 1.0 / .70 / .90 от 48 пикс, допуск .12), острота кончика (ширина на .8 длины / длина, .10-.40), заполнение круга .5R >= .90 (теория A+B .95; дырка кольца №834 даёт 0).
#   Малая звезда B (5 лучей, светлее, плывёт) лежит внутри — на проверку лучей A не влияет (кончики A дальше).
# usage: rasterdoor.py снимок.png -> числа и PASS/FAIL; код возврата 0 / 1
import sys, math
import numpy as np
from PIL import Image
im = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
lum = im.mean(axis=2); H, W = lum.shape
CX, CY, R0 = 240, 116, 48.0
ANG = [.06, 1.62, 3.20, 4.70]; LEN = [.80, 1.0, .70, .90]
STEP = .5   # градусов
NA = int(360 / STEP)
def prof():
    r = np.zeros(NA)
    for k in range(NA):
        a = math.radians(k * STEP); d = 0.0
        while d < 120:
            x = CX + math.cos(a) * d; y = CY - math.sin(a) * d
            if not (0 <= int(round(x)) < W and 0 <= int(round(y)) < H) or lum[int(round(y)), int(round(x))] < 70: break
            d += .25
        r[k] = d
    return r
r = prof(); bad = 0
def fill(rc):
    seen = set(); st = [(CX, CY)]; tot = inner = 0
    if lum[CY, CX] < 70: return 0.0
    while st:
        x, y = st.pop()
        if (x, y) in seen or not (0 <= x < W and 0 <= y < H) or lum[y, x] < 70 or abs(x - CX) > 125 or abs(y - CY) > 125: continue
        seen.add((x, y)); tot += 1; inner += math.hypot(x - CX, y - CY) <= rc; st += [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    return inner / (math.pi * rc * rc)
body = fill(.5 * R0)
print(f"заполнение круга .5R {body:.2f}")
if body < .90: print(f"  FAIL заполнение {body:.2f} < .90 (дырка кольца или тонкие лучи)"); bad += 1
tws = []
for a, L in zip(ANG, LEN):
    k0 = int(round(math.degrees(a) / STEP)) % NA
    win = [(k0 + j) % NA for j in range(-int(8 / STEP), int(8 / STEP) + 1)]; kk = max(win, key=lambda k: r[k]); Lm = r[kk]
    lim = .8 * Lm; n = 0
    for sgn in (1, -1):
        j = 0
        while j < int(45 / STEP) and r[(kk + sgn * j) % NA] >= lim: j += 1
        n += j - .5
    tw = n * STEP * math.pi / 180 * lim / Lm if Lm > 0 else 9; tws.append(tw)
    print(f"луч на {math.degrees(a):.0f}°: длина {Lm:.1f} пикс ({Lm / R0:.2f}), нужно {L:.2f}, ширина кончика на .8 длины {tw:.2f}")
    if abs(Lm / R0 - L) > .12: print(f"  FAIL луч {math.degrees(a):.0f}°: длина {Lm / R0:.2f}, нужно {L:.2f} ± .12"); bad += 1
    if not (.10 <= tw <= .40): print(f"  FAIL луч {math.degrees(a):.0f}°: кончик {tw:.2f} вне .10-.40"); bad += 1
print("PASS glint944 rasterdoor" if not bad else "FAIL glint944 rasterdoor"); sys.exit(1 if bad else 0)
