#!/usr/bin/env python3
"""Гейт №898: под фермой/мостом L1 L5-5 глаз камеры не прыгает вверх над перекрытием.
python3 camfloor898.py smoke.txt [--red]   smoke.txt — прогон camfloor898.txt (CAMF, TELEPORT); --red — ждём провал (прогон с flag camflooroverold 1)
Мера: шаг глаза относительно машины за кадр (м); 4,5 с после телепорта (goto, посадка за руль) не считаются. PASS: нет кадров с шагом > 1,0 м."""
import re, sys, math
red = '--red' in sys.argv; f = [a for a in sys.argv[1:] if not a.startswith('--')][0]
R = re.compile(r'CAMF t=(\S+) st=\d+ fov=\S+ eye=([-\d.]+),([-\d.]+),([-\d.]+) look=\S+ homer=\S+ car=([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)')
tp, rows, cov, scene = [], [], {}, None   # cov: сцена -> кадры машины в полосе фермы (z -290..-210) и их наибольший боковой уход от полосы
BAND, LANE_TOL, BAND_MIN = (-290.0, -210.0), 3.0, 20
for l in open(f, errors='replace'):
    m = re.match(r'SCENE r\d_(\d+)_', l)
    if m: scene = int(m.group(1)); cov[scene, len([k for k in cov if k[0] == scene])] = [0, 0.0]
    m = re.match(r'TELEPORT t=(\S+) kind=(goto|foot|repair)', l)
    if m: tp.append(float(m.group(1)))
    m = R.match(l)
    if m:
        rows.append([float(x) for x in m.groups()])
        if scene is not None and BAND[0] <= rows[-1][6] <= BAND[1]:
            c = cov[[k for k in cov if k[0] == scene][-1]]; c[0] += 1; c[1] = max(c[1], abs(rows[-1][4] - scene))
big, worst = [], 0.0
for a, b in zip(rows, rows[1:]):
    if any(-0.3 <= b[0] - t < 4.5 for t in tp): continue
    rel = math.dist([b[1] - b[4], b[2] - b[5], b[3] - b[6]], [a[1] - a[4], a[2] - a[5], a[3] - a[6]])
    worst = max(worst, rel)
    if rel > 1.0: big.append((b[0], rel, b[4], b[6]))
print(f'кадров {len(rows)}, телепортов {len(tp)}, наибольший шаг глаза относительно машины {worst:.2f} м, кадров с шагом > 1,0 м: {len(big)}')
for t, r, x, z in big[:12]: print(f'  t={t:.2f} шаг {r:.2f} м, машина x={x:.0f} z={z:.0f}')
# №898 (Надзор 23.10): полоса, где машина упёрлась ДО фермы, ничего не проверяет — каждый проезд обязан пройти полосу фермы по своей полосе
thin = [(k[0], v[0], v[1]) for k, v in cov.items() if v[0] < BAND_MIN or v[1] > LANE_TOL]
print('проездов %d, проехали ферму по своей полосе: %d; не проехали: %s' % (len(cov), len(cov) - len(thin), ['полоса %d кадров %d уход %.1f м' % t for t in thin]))
ok = not big and not thin and len(cov) >= 6
print('PASS' if ok != red else 'FAIL'); sys.exit(0 if ok != red else 1)
