#!/usr/bin/env python3
"""Глаз камер комнат не в стене (16.10, Камера; Mac, без эмулятора): для комнат уровня N Гомер в узлах пола 1 м, глаз — как в EBOOT (viewer/roomcam.c через tests/rooms/view_host.c),
расстояние от глаза до ближайшего треугольника РИСОВАНИЯ комнаты (пакет interiors-lN-gfx.bin). Меньше NEAR_M (ближняя плоскость) — стена в плоскости камеры (мигание/срез кадра);
меньше IN_M — глаз у самой поверхности. Камеры комнат авторские (правило глаза города не применяется), цель — найти точки данных, где кадр упирается в стену.
  .venv/bin/python tests/rooms/eye_wall_check.py N [DATA]   (DATA по умолчанию build/t24d_emu копии Сборки)"""
import os, subprocess, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests/rooms'))
import shr7read, roomorient, walls
NEAR_M, IN_M = 0.30, 0.05


def ptri(P, A, B, C):
    """расстояние от точек P (n,3) до треугольников (m,3)x3 -> (n,m) (Эриксон)"""
    out = np.empty((len(P), len(A)))
    for i, p in enumerate(P):
        ab, ac, ap = B - A, C - A, p - A
        d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
        bp = p - B; d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
        cp = p - C; d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
        vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4
        den = va + vb + vc; den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        v = vb / den; w = vc / den
        q = A + ab * v[:, None] + ac * w[:, None]
        # вне треугольника — ближайшая точка на рёбрах
        def seg(a, b):
            ba = b - a; t = np.clip(((p - a) * ba).sum(1) / np.where((ba * ba).sum(1) < 1e-12, 1e-12, (ba * ba).sum(1)), 0, 1); return a + ba * t[:, None]
        inside = (v >= 0) & (w >= 0) & (v + w <= 1)
        cands = [seg(A, B), seg(B, C), seg(C, A)]
        dq = np.linalg.norm(p - q, axis=1)
        de = np.min([np.linalg.norm(p - c, axis=1) for c in cands], axis=0)
        out[i] = np.where(inside, dq, de)
    return out


def main():
    n = int(sys.argv[1]); data = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / 'Downloads/shar-psp-sonnet-16b-w/build/t24d_emu'
    sub = '' if n == 1 else f'l{n}/'
    pkg = data / f'{sub}interiors-l{n}-gfx.bin'; col = data / f'{sub}interiors-l{n}.bin'
    rooms = shr7read.load_rooms(str(pkg)); cols = walls.rooms_col(col); host = roomorient.view_host()
    req = []
    for name, (TR, BX) in cols.items():
        if name in rooms: req += [f'{name} {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}' for p in roomorient.floor_points(TR, BX, 1.0)]
    res = subprocess.run([str(host), str(pkg)], input='\n'.join(req) + '\n', capture_output=True, text=True, check=True).stdout.splitlines()
    worst_all = 0
    for name, d in rooms.items():
        views = [l.split() for l in res if l.startswith('VIEW ' + name + ' ') and l.split()[5] != '-1']
        if not views: print(f'L{n} {name}: кадров нет'); continue
        P = np.asarray(d['P'], np.float64).reshape(-1, 3, 3)
        by = {}
        for v in views:
            eye = np.array([float(x) for x in v[8:11]]); by.setdefault(v[6], []).append(eye)
        for cam, eyes in sorted(by.items()):
            E = np.unique(np.round(np.array(eyes), 2), axis=0)
            if len(E) > 150: E = E[:: len(E) // 150 + 1]
            dist = ptri(E, P[:, 0], P[:, 1], P[:, 2]).min(1)
            k = int(np.argmin(dist)); m = dist[k]
            tag = ' <<< В СТЕНЕ (< %.2f)' % IN_M if m < IN_M else (' <- ближе ближней плоскости (< %.2f)' % NEAR_M if m < NEAR_M else '')
            if m < IN_M: worst_all += 1
            print(f'L{n} {name:22s} {cam:24s} глаз-точек {len(E):3d} мин. расстояние до стены {m:.2f} м ({E[k][0]:.1f},{E[k][1]:.1f},{E[k][2]:.1f}){tag}')
    print(f'итог L{n}: камер с глазом у самой поверхности (< {IN_M} м): {worst_all}')


main()
