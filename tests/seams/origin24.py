#!/usr/bin/env python3
"""Правка Роба 106 (повтор 01.10: «швы, ещё больше полосы на дороге везде»): центры кусков города точны в 24-бит float GE.

GE берёт матрицу модели 24-битными float (sceGuSetMatrix шлёт старшие 24 бита float32). Сцена без диска: дорога 40 x 200 м
в 600–900 м от начала уровня, нарезана на куски ~8 x 8 м разной ширины, как режет экспортёр (у каждого куска свой центр). Вершины —
общая решётка 2^-9 м (правка 37), центры — tools/psp_export.py grid_quant. Кадр — растеризатор GE tools/seams_raster.py
(GE24: сдвиг куска усечён до 24 бит, как на PSP), камера за машиной на дороге, 5 точек вдоль неё.
  без ключа       — центры по правилу ORIGIN_STEP 1/16 м: щелей на дороге 0 (код 0)
  --rule grid     — центры на решётке 2^-9 м, как до правки: щели вдоль стыков кусков — обязан упасть (код 1)
Запуск: .venv/bin/python tests/seams/origin24.py [--rule grid]"""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import seams_raster as S   # noqa: E402
import psp_export as E   # noqa: E402  (grid_quant — правило экспортёра; диск при импорте не читается)

G = 2.0 ** -9


def pieces():
    """дорога 40 x 200 м кусками ~8 x 8 м разной ширины (как режет экспортёр: по числу вершин, края где придётся),
    внутри — по 4 x 4 квада; общие края кусков совпадают на решётке 2^-9 м"""
    rng = np.random.default_rng(106)
    x0, z0 = 613.0917, 690.137
    xs = np.round((x0 - 20 + np.r_[0, np.cumsum(rng.uniform(6.5, 9.5, 5))]) / G) * G
    zs = np.round((z0 + np.r_[0, np.cumsum(rng.uniform(6.5, 9.5, 25))]) / G) * G
    out = []
    for i in range(len(zs) - 1):
        for j in range(len(xs) - 1):
            gx, gz = np.linspace(xs[j], xs[j + 1], 5), np.linspace(zs[i], zs[i + 1], 5)
            T = []
            for k in range(4):
                for m in range(4):
                    a, b, c, d = (gx[m], 0, gz[k]), (gx[m + 1], 0, gz[k]), (gx[m + 1], 0, gz[k + 1]), (gx[m], 0, gz[k + 1])
                    T += [(a, b, c), (a, c, d)]
            P = np.round(np.array(T, np.float64).reshape(-1, 3) / G) * G   # общая решётка
            c, q, _ = E.grid_quant(P, E.CITY_GRID)   # правило экспортёра как есть
            o = S.f24(c.astype(np.float32)) if S.GE24 else c.astype(np.float32)
            W = (o[None] + q.astype(np.float32) * np.float32(G)).astype(np.float32).reshape(-1, 3, 3)
            out.append((P.min(0), P.max(0), 0, W, W, 0))
    return out, x0, z0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rule', default='origin24'); a = ap.parse_args()
    E.ORIGIN24 = a.rule != 'grid'
    step = E.ORIGIN_STEP if E.ORIGIN24 else E.CITY_GRID
    pcs, x0, z0 = pieces()
    L = S.lib(); holes = 0
    for j, t in enumerate(np.linspace(10, 150, 5)):
        x = x0 + (j - 2) * 1.7
        car = np.array([x, 0.0, z0 + t])
        eye = car + [0.0, S.CAM_UP, -S.CAM_BACK]; at = car + [0.0, S.CAM_LOOK, 1.0]
        cov, dep, gb = S.frame(L, pcs, eye, at)
        holes += int(S.on_ground(S.thin_holes(cov) | S.through(cov, dep), cov & gb).sum())
    ok = holes == 0
    print(f'{"OK" if ok else "FAIL"} ({a.rule}, шаг центра {step:g} м): щелей на дороге в 5 кадрах GE24 — {holes}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
