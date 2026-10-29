#!/usr/bin/env python3
"""Сценарий tests/rooms/emu_cams.txt: снимок из каждой камеры комнат уровня 1 (пункт 11.2). Вход — через дверь, дальше Гомер
ставится в центр первого триггера каждой камеры (foot с Y под городом — внутри той же комнаты); если центр в триггере выхода
(с радиусом тела 0.3 м), точка сдвигается вглубь триггера камеры, иначе сработал бы выход. Точки — по пакету build/interiors-l1*.bin
(данные диска), через tests/rooms/cams_host.c; триггеры выхода — из build/interiors-l1.json.
  .venv/bin/python tests/rooms/emu_cams_gen.py   (после tests/rooms/cams.sh: нужен build/rooms_cams/host.txt)"""
import json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
rows = [l.split() for l in (ROOT / 'build/rooms_cams/host.txt').read_text().splitlines() if l.startswith('CAM ')]
exits = {r['name']: r['exitTrig'] for r in json.loads((ROOT / 'build/interiors-l1.json').read_text())['rooms']}
DOOR = {'KwikEMart': ('kwik', 'foot 213.9 299 0 5.2', 1.5), 'SpringfieldElementary': ('school', 'foot -31.5 589.45 -1.5708 4.64', 3),
        'SimpsonsHouse': ('house', 'foot 228.94 180.5 0 3.83', 3)}


def in_exit(t, p, r=0.3):
    kind, c, h, ax = t; d = [p[i] - c[i] for i in range(3)]
    e2 = sum(max(abs(sum(d[i] * ax[k][i] for i in range(3))) - h[k], 0.0) ** 2 for k in range(3))
    return e2 <= r * r


out = ['# Снимок из каждой камеры комнат уровня 1 (пункт 11.2, tests/rooms/emu.sh --cams). Сгенерирован tests/rooms/emu_cams_gen.py:',
       '# вход через дверь, потом Гомер в центре первого триггера каждой камеры; HOMER ... cam=ИМЯ — какую камеру выбрал движок',
       'scene start', 'wait 3']
seen = set()
for room in ('KwikEMart', 'SpringfieldElementary', 'SimpsonsHouse'):
    tag, foot, w = DOOR[room]
    out += [f'scene {tag}_door', foot, f'wait {w}', 'press up 0.3', 'press circle 0.3', 'wait 1', 'press triangle', 'wait 2']   # правка 41: вход по △; ○ — бегом, как игрок
    for r in rows:
        if r[1] != room or r[5] != '0' or r[3] in seen: continue
        seen.add(r[3]); p = [float(r[6]), float(r[7]), float(r[8])]; ex = exits[room]
        if ex and in_exit(ex, p):   # вглубь комнаты — прочь от центра триггера выхода по горизонтали
            dx, dz = p[0] - ex[1][0], p[2] - ex[1][2]; l = math.hypot(dx, dz) or 1.0
            if l < 1e-3: dx, dz, l = 0.0, -1.0, 1.0
            while in_exit(ex, p): p[0] += dx / l * .1; p[2] += dz / l * .1
        short = r[3].replace('int_kwik_camera', 'kc').replace('int_ele_', 'se_').replace('int_sh_', 'sh_')
        out += [f'scene {short}', f'foot {p[0]:.3f} {p[2]:.3f} 0 {p[1] + 0.5:.2f}', 'wait 1.5', f'shot {short}']
out.append('end')
(ROOT / 'tests/rooms/emu_cams.txt').write_text('\n'.join(out) + '\n'); print(len(seen), 'камер ->', 'tests/rooms/emu_cams.txt')
