#!/usr/bin/env python3
"""Сценарий замера пурпура ходячей камерой на ДОСТИЖИМЫХ местах (16.10, Камера, по просьбе дирижёра): маршруты кнопками от входа в комнату, как tests/rooms/house_route.txt Стен
(поворот press left/right/down 0,35–0,55 с, потом press up 1,6 с, кадр), вход через каждую дверь города заново на каждый маршрут. Гомер ходит сам, недостижимые точки невозможны.
Маршруты детерминированные (seed от уровня/комнаты/номера), повороты чередуются с прямыми так, чтобы покрыть комнату; ROUTES маршрутов по SEGS отрезков.
  .venv/bin/python tests/rooms/purple_route_gen.py N [ROUTES=4] [SEGS=18] > сценарий"""
import math, os, random, struct, sys
from pathlib import Path
n = int(sys.argv[1]); ROUTES = int(sys.argv[2]) if len(sys.argv) > 2 else 4; SEGS = int(sys.argv[3]) if len(sys.argv) > 3 else 18
DATA = Path(os.environ.get('DATA', Path.home() / 'Downloads/shar-psp-sonnet-16b-w/build/t24d_emu')); sub = '' if n == 1 else f'l{n}/'
d = (DATA / f'{sub}interiors-l{n}.bin').read_bytes(); _, nr, nd, ver = struct.unpack_from('<4sIII', d, 0)
names, off = [], 16
for i in range(nr): names.append(d[off:off + 32].split(b'\0')[0].decode()); off += 128
doors = []
for i in range(nd):
    b = d[off:off + 128]; x, y, z = struct.unpack_from('<3f', b, 32); idx, = struct.unpack_from('<i', b, 44); h, = struct.unpack_from('<f', b, 48); doors.append((idx, x, y, z, h)); off += 128
out = [f'# Пурпур ходячей камерой по маршрутам кнопками, L{n} (tests/rooms/purple_route_gen.py): {ROUTES} маршрута по {SEGS} отрезков в каждой комнате; фон комнат закрашен пурпуром']
out += ['scene start', 'wait 3']
if n > 1: out += [f'scene L{n}_load', f'flag golevel {n}', 'wait 20']
for (idx, x, y, z, h) in doors:
    rname = names[idx]; hin = math.atan2(math.sin(h + math.pi), math.cos(h + math.pi)); fx, fz = x - 3.7 * math.sin(hin), z - 3.7 * math.cos(hin)
    for r in range(ROUTES):
        rnd = random.Random(f'{n}-{rname}-{r}')
        out += [f'scene {rname[:6]}_in{r}', f'foot {fx:.2f} {fz:.2f} {hin:.4f} {y + 0.4:.2f}', 'wait 1.5', 'press up 0.3', 'press circle 0.3', 'wait 1', 'press triangle', 'wait 2', 'flag camlog']
        for k in range(SEGS):
            turn = rnd.choice(['left', 'right', 'left', 'right', 'down']); dur = rnd.choice([0.35, 0.45, 0.55])
            fwd = rnd.choice([1.0, 1.6, 1.6, 2.2])
            out += [f'scene {rname[:6]}_{r}_{k:02d}', f'press {turn} {dur}', 'wait 0.5', f'press up {fwd}', f'wait {fwd + 0.3:.1f}', f'shot {rname[:6]}_{r}_{k:02d}']
out.append('end'); print('\n'.join(out))
