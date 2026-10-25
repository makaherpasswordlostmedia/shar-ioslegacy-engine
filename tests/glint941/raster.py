#!/usr/bin/env python3
# №941 гейт формы по растру эмулятора: снимок листа форм (flag glintlab, tests/glint941/lab.txt): четыре звезды в ряд — A, B (путь блика spritelight),
# звезда стекла (kind 3) и звезда частиц (kind 1), центры (60 + 120 i, 116), радиус 48 пикс. Мерим по картинке, не по коду:
#   лучей (пики радиуса по углу), доля тела (площадь внутри r <= .5 Rmax / вся), острота кончика (ширина на .8 длины луча / длина), впадина (радиус впадин / Rmax).
# usage: raster.py снимок.png            -> печатает числа и PASS/FAIL по порогам; код возврата 0 / 1
import sys, math
import numpy as np
from PIL import Image
im = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
lum = im.mean(axis=2); H, W = lum.shape
CY = 116
EXPECT = [('A', 4), ('B', 5), ('стекло', 4), ('частицы', 4)]
def prof(cx, cy):
    r = np.zeros(180)
    for k in range(180):
        a = math.radians(k * 2); d = 0.0
        while d < 70:
            x = cx + math.cos(a) * d; y = cy - math.sin(a) * d
            if not (0 <= int(round(x)) < W and 0 <= int(round(y)) < H) or lum[int(round(y)), int(round(x))] < 90: break
            d += .25
        r[k] = d
    return r
def area_in(cx, cy, rmax_cut):
    # компонента, связанная с центром: заливка
    seen = set(); st = [(cx, cy)]; pts = []
    while st:
        x, y = st.pop()
        if (x, y) in seen or not (0 <= x < W and 0 <= y < H) or lum[y, x] < 90 or abs(x - cx) > 62 or y < 62 or y > 200: continue
        seen.add((x, y)); pts.append((x, y)); st += [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    tot = len(pts); inner = sum(1 for (x, y) in pts if math.hypot(x - cx, y - cy) <= rmax_cut)
    return tot, inner
bad = 0; res = []
for i, (name, nexp) in enumerate(EXPECT):
    cx = 60 + 120 * i; r = prof(cx, CY); rs = np.convolve(np.r_[r[-3:], r, r[:3]], np.ones(7) / 7, 'valid'); Rm = rs.max()
    peaks = []
    for k in range(180):
        w = [rs[(k + j) % 180] for j in range(-15, 16)]
        if rs[k] == max(w) and rs[k] > .55 * Rm and rs[k] - min(w) > .15 * Rm and not any(abs(((k - p + 90) % 180) - 90) < 8 for p, _ in peaks): peaks.append((k, rs[k]))
    vals = []
    for a, b in zip(peaks, peaks[1:] + peaks[:1]):
        span = (b[0] - a[0]) % 180; vals.append(min(rs[(a[0] + j) % 180] for j in range(span + 1)))
    valley = float(np.mean(vals)) / Rm if vals else 0
    tw = []
    for k, L in peaks:
        lim = .8 * L; n = 0
        for sgn in (1, -1):
            j = 0
            while j < 45 and r[(k + sgn * j) % 180] >= lim: j += 1
            n += j - .5
        tw.append(n * 2 * math.radians(1) * lim / L)   # дуга на .8 L (шаг 2° -> j шагов) / L
    tot, inner = area_in(cx, CY, .6 * Rm)
    body = inner / (math.pi * (.6 * Rm) ** 2)   # заполнение круга r = .6 Rmax вокруг центра: пухлое тело ~ полный круг, игла ~ крест
    res.append((name, len(peaks), Rm, body, float(np.mean(tw)) if tw else 9, valley))
    print(f"{name}: лучей {len(peaks)} (нужно {nexp}), радиус {Rm:.1f} пикс, заполнение круга .6R {body:.2f}, ширина кончика на .8 длины {np.mean(tw) if tw else 9:.2f}, впадины {valley:.2f}")
    if len(peaks) != nexp: print(f"  FAIL {name}: лучей {len(peaks)}, нужно {nexp}"); bad += 1
    if body < .87: print(f"  FAIL {name}: заполнение круга .6R {body:.2f} < .87 (тело не пухлое: лучи-иглы или снежинка)"); bad += 1
    twm = float(np.mean(tw)) if tw else 9
    if not (.25 <= twm <= .36): print(f"  FAIL {name}: кончик {twm:.2f} вне .25-.36 (меньше — игла, больше — тупой ромб)"); bad += 1
    if not (.45 <= valley <= .66): print(f"  FAIL {name}: впадины {valley:.2f} вне .45-.66 (излом или тонкая астроида)"); bad += 1
print("PASS glint941 raster" if not bad else "FAIL glint941 raster"); sys.exit(1 if bad else 0)
