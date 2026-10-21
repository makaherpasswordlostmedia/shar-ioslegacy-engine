#!/usr/bin/env python3
"""Гейт №701: небо уровня закрывает все направления. Из центра купола (небо рисуется вокруг камеры) пускаем лучи по азимуту 0..360 (шаг 5°) и
подъёму 2..80° (шаг 3°): в каждом направлении должен быть хотя бы один треугольник неба (owner 2 в level.shr). Красный контроль: --drop N убирает сектор
из N-го азимутального куска (45° по центрам треугольников) — гейт обязан упасть.
  python3 tests/sky/coverage_gate.py LEVEL.shr [--drop N]    код 0 — без пустот, 1 — есть пустые направления"""
import sys, numpy as np
sys.path.insert(0, 'tools')
import shr7read as R
def main():
    path = sys.argv[1]; drop = int(sys.argv[sys.argv.index('--drop') + 1]) if '--drop' in sys.argv else -1
    d = R.load(path, owner=2); sky = d['P']
    if drop >= 0:
        cen = sky.mean(1); sec = np.floor((np.arctan2(cen[:, 0], cen[:, 2]) + np.pi) / (np.pi / 4)).astype(int) % 8
        sky = sky[sec != drop]
    v0 = sky[:, 0]; e1 = sky[:, 1] - v0; e2 = sky[:, 2] - v0; empty = []
    for az in range(0, 360, 5):
        for el in range(2, 81, 3):
            a, e = np.radians(az), np.radians(el); dv = np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])
            h = np.cross(dv, e2); det = (e1 * h).sum(1); ok = np.abs(det) > 1e-12; f = np.where(ok, 1 / np.where(ok, det, 1), 0)
            s = -v0; u = f * (s * h).sum(1); q = np.cross(s, e1); v = f * (dv * q).sum(1); t = f * (e2 * q).sum(1)
            if not (ok & (u >= -1e-4) & (v >= -1e-4) & (u + v <= 1 + 1e-4) & (t > 0)).any(): empty.append((az, el))
    print(f'{path}: треугольников неба {len(sky)}, пустых направлений {len(empty)}' + (f' (пример {empty[:4]})' if empty else ''))
    return 1 if empty else 0
if __name__ == '__main__': sys.exit(main())
