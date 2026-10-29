#!/usr/bin/env python3
"""Сценарий замера пурпура (дыр в стенах) ходячей камерой во ВСЕХ комнатах уровня N (16.10, Камера, в помощь Стенам к №301): по образцу tests/rooms/house_grid.txt
(сетка пола 2,5 м, два курса 0 и π), вход через каждую дверь города, фон комнат в пакете закрашен пурпуром (tests/rooms/see_through.py paint). Точки в триггере выхода пропускаются.
  .venv/bin/python tests/rooms/purple_grid_gen.py N > сценарий   (DATA — каталог набора, по умолчанию build/t24d_emu копии Сборки)
Разбор: tests/rooms/purple_report.py (пурпурных пикселей на кадр, rc= из CAMF: только ходячая камера rc=0)."""
import math, os, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests/rooms'))
import roomorient, walls
n = int(sys.argv[1]); DATA = Path(os.environ.get('DATA', Path.home() / 'Downloads/shar-psp-sonnet-16b-w/build/t24d_emu'))
sub = '' if n == 1 else f'l{n}/'
col = DATA / f'{sub}interiors-l{n}.bin'
d = col.read_bytes(); _, nr, nd, ver = struct.unpack_from('<4sIII', d, 0)
rooms, off = [], 16
for i in range(nr):
    b = d[off:off + 128]; name = b[:32].split(b'\0')[0].decode(); kind = struct.unpack_from('<I', b, 64)[0]; sy = struct.unpack_from('<f', b, 36)[0]; sx, sz = struct.unpack_from('<f', b, 32)[0], struct.unpack_from('<f', b, 40)[0]
    trig = None if kind == 0xFFFFFFFF else (kind, struct.unpack_from('<3f', b, 68), struct.unpack_from('<3f', b, 80), [struct.unpack_from('<3f', b, 92 + 12 * k) for k in range(3)])
    rooms.append((name, trig, sy, sx, sz)); off += 128
doors = []
for i in range(nd):
    b = d[off:off + 128]; x, y, z = struct.unpack_from('<3f', b, 32); idx, = struct.unpack_from('<i', b, 44); h, = struct.unpack_from('<f', b, 48); doors.append((idx, x, y, z, h)); off += 128
cols = walls.rooms_col(col)


def in_exit(t, p, r=0.5):
    if not t: return False
    kind, c, h, ax = t; dd = [p[i] - c[i] for i in range(3)]
    e2 = sum(max(abs(sum(dd[i] * ax[k][i] for i in range(3))) - h[k], 0.0) ** 2 for k in range(3))
    return e2 <= r * r


R_BODY, CELL, STEP_MAX = 0.35, 0.25, 0.6


def reachable(TR, BX, sx, sz, pts):
    """точки сетки 2,5 м, до которых Гомер доходит пешком от старта комнаты: заливка по клеткам пола 0,25 м (земля COL1 минус ящики мебели), стены — негоризонтальные грани
    COL1 на высоте 0,2..1,6 м над полом ближе R_BODY (0,35 м) к клетке, ступень пола не выше STEP_MAX между соседними клетками. Приближение к коллизии движка, не её копия:
    лишнее отсеивает недостижимое за арками/мебелью, как просил дирижёр (кадры с телепорта foot в недоступных местах дают ложную тревогу)."""
    fine = roomorient.floor_points(TR, BX, CELL)
    if not len(fine) or not len(pts): return pts
    wall = TR[TR[:, 3, 1] <= .7][:, :3]   # (m,3,3)
    key = lambda x, z: (int(round(x / CELL)), int(round(z / CELL)))
    cells = {key(p[0], p[2]): p for p in fine}
    # стены: отрезки на плоскости xz (рёбра), только на высоте тела над полом комнаты
    segs = []
    for t in wall:
        ymin, ymax = t[:, 1].min(), t[:, 1].max()
        for a, b in ((0, 1), (1, 2), (2, 0)): segs.append((t[a, 0], t[a, 2], t[b, 0], t[b, 2], ymin, ymax))
    S = np.array(segs) if segs else np.zeros((0, 6))
    blocked = set()
    if len(S):
        for k, p in cells.items():
            fl = p[1]; m = (S[:, 5] > fl + .2) & (S[:, 4] < fl + 1.6)
            if not m.any(): continue
            A = S[m]; ax, az, bx, bz = A[:, 0], A[:, 1], A[:, 2], A[:, 3]
            dx, dz = bx - ax, bz - az; L2 = np.maximum(dx * dx + dz * dz, 1e-9)
            t = np.clip(((p[0] - ax) * dx + (p[2] - az) * dz) / L2, 0, 1)
            d = np.hypot(p[0] - (ax + t * dx), p[2] - (az + t * dz))
            if (d < R_BODY).any(): blocked.add(k)
    start = min(cells, key=lambda k: (cells[k][0] - sx) ** 2 + (cells[k][2] - sz) ** 2)
    seen = {start}; q = [start]
    while q:
        c = q.pop()
        for dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n_ = (c[0] + dk[0], c[1] + dk[1])
            if n_ in seen or n_ not in cells or n_ in blocked: continue
            if abs(cells[n_][1] - cells[c][1]) > STEP_MAX: continue
            seen.add(n_); q.append(n_)
    keep = []
    for p in pts:
        k = key(p[0], p[2]); near = [(k[0] + i, k[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        if any(c in seen for c in near): keep.append(p)
    print(f'# достижимо: сетка {len(pts)} -> {len(keep)}, клеток пола {len(cells)}, достижимых {len(seen)}, заблокировано стеной {len(blocked)}', file=sys.stderr)
    return np.array(keep)


out = [f'# Пурпур ходячей камерой, L{n}: сетка пола 2,5 м, два курса (tests/rooms/purple_grid_gen.py); пакет интерфейса комнат закрашен (фон 0xFFFF00FF)', 'scene start', 'wait 3']
if n > 1: out += [f'scene L{n}_load', f'flag golevel {n}', 'wait 20']
total = 0
for (idx, x, y, z, h) in doors:
    rname, ex, sy, rsx, rsz = rooms[idx]; hin = math.atan2(math.sin(h + math.pi), math.cos(h + math.pi)); fx, fz = x - 3.7 * math.sin(hin), z - 3.7 * math.cos(hin)
    out += [f'scene {rname}_door', f'foot {fx:.2f} {fz:.2f} {hin:.4f} {y + 0.4:.2f}', 'wait 1.5', 'press up 0.3', 'press circle 0.3', 'wait 1', 'press triangle', 'wait 2', 'flag camlog']
    TR, BX = cols[rname]; pts = reachable(TR, BX, rsx, rsz, roomorient.floor_points(TR, BX, 2.5)); k = 0
    for p in pts:
        if in_exit(ex, p): continue
        for hd, tag in ((0.0, 'a'), (math.pi, 'b')):
            k += 1; out += [f'scene {rname[:6]}_{k:03d}', f'foot {p[0]:.3f} {p[2]:.3f} {hd:.4f} {sy + 0.5:.2f}', 'wait 1.0', f'shot {rname[:6]}_{k:03d}']
    total += k
out.append('end'); print('\n'.join(out)); print(f'# кадров {total}', file=sys.stderr)
