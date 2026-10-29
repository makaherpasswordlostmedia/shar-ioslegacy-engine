#!/usr/bin/env python3
"""Сценарий камер комнат уровня N (1..7), глаз не в стене (16.10, Камера): вход через КАЖДУЮ дверь города, потом Гомер в центре первого триггера каждой камеры комнаты
(как tests/rooms/emu_cams_gen.py для L1, но двери и камеры — из пакета уровня); на каждой точке CAMIN (eye/near) и кадр.
  .venv/bin/python tests/rooms/emu_cams_levels_gen.py N > сценарий   (нужны interiors-lN.bin и вывод cams_host по interiors-lN-gfx.bin)
  Аргументы окружения: DATA=каталог набора (по умолчанию build/t24d_emu из копии Сборки), CAMS=файл вывода cams_host"""
import math, os, struct, sys
n = int(sys.argv[1]); DATA = os.environ.get('DATA', os.path.expanduser('~/Downloads/shar-psp-sonnet-16b-w/build/t24d_emu'))
sub = '' if n == 1 else f'l{n}/'
d = open(f'{DATA}/{sub}interiors-l{n}.bin', 'rb').read(); _, nr, nd, ver = struct.unpack_from('<4sIII', d, 0)
rooms, off = [], 16
for i in range(nr):
    b = d[off:off + 128]; name = b[:32].split(b'\0')[0].decode(); kind = struct.unpack_from('<I', b, 64)[0]; sy = struct.unpack_from('<f', b, 36)[0]
    trig = None if kind == 0xFFFFFFFF else (kind, struct.unpack_from('<3f', b, 68), struct.unpack_from('<3f', b, 80), [struct.unpack_from('<3f', b, 92 + 12 * k) for k in range(3)])
    rooms.append((name, trig, sy)); off += 128
doors = []
for i in range(nd):
    b = d[off:off + 128]; x, y, z = struct.unpack_from('<3f', b, 32); idx, = struct.unpack_from('<i', b, 44); h, = struct.unpack_from('<f', b, 48); doors.append((idx, x, y, z, h)); off += 128
cams = [l.split() for l in open(os.environ['CAMS']).read().splitlines() if l.startswith('CAM ')]


def in_exit(t, p, r=0.3):
    if not t: return False
    kind, c, h, ax = t; dd = [p[i] - c[i] for i in range(3)]
    e2 = sum(max(abs(sum(dd[i] * ax[k][i] for i in range(3))) - h[k], 0.0) ** 2 for k in range(3))
    return e2 <= r * r


out = [f'# Камеры комнат L{n}, глаз не в стене (tests/rooms/emu_cams_levels_gen.py): двери {len(doors)}, камер {len(cams)}; CAMIN eye/near на каждой точке', 'scene start', 'wait 3']
if n > 1: out += [f'scene L{n}_load', f'flag golevel {n}', 'wait 20']
seen = set()
for (idx, x, y, z, h) in doors:
    rname = rooms[idx][0]; hin = h + math.pi
    hin = math.atan2(math.sin(hin), math.cos(hin)); fx, fz = x - 3.7 * math.sin(hin), z - 3.7 * math.cos(hin)
    out += [f'scene {rname}_door', f'foot {fx:.2f} {fz:.2f} {hin:.4f} {y + 0.4:.2f}', 'wait 1.5', 'press up 0.3', 'press circle 0.3', 'wait 1', 'press triangle', 'wait 2']
    for r in cams:
        if r[1] != rname or r[5] != '0' or (rname, r[3]) in seen: continue
        seen.add((rname, r[3])); p = [float(r[6]), float(r[7]), float(r[8])]; ex = rooms[idx][1]
        if ex and in_exit(ex, p):
            dx, dz = p[0] - ex[1][0], p[2] - ex[1][2]; l = math.hypot(dx, dz) or 1.0
            if l < 1e-3: dx, dz, l = 0.0, -1.0, 1.0
            while in_exit(ex, p): p[0] += dx / l * .1; p[2] += dz / l * .1
        short = f'{rname[:4]}_{r[3].split("camera")[-1] if "camera" in r[3] else r[3][-6:]}'
        # высота Гомера от пола комнаты (старт y), не от триггера: на триггере Мо камеры 05 Гомер вставал на что-то над потолком (y -15,6) и кадр уходил в потолок
        out += [f'scene {short}', f'foot {p[0]:.3f} {p[2]:.3f} 0 {rooms[idx][2] + 0.5:.2f}', 'wait 0.5', 'flag camin 1', 'wait 1.5', 'flag camin 1', f'shot {short}']
out.append('end'); print('\n'.join(out))
