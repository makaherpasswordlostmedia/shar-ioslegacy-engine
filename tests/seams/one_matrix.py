#!/usr/bin/env python3
"""Правки Роба 224/237/251 («швы очень мигают»): одна матрица на клетку и город в осях камеры — без диска, на модели GE float24.

Сцена: дорога 40 x 200 м в 600–900 м от начала уровня, нарезана на куски ~8 x 8 м разной ширины (как режет экспортёр: клетка
40 м × текстура), внутри — квады, общие края кусков совпадают точно (вершины на решётке 2^-9 м). Кадр — модель GE
tools/seams_ge.py: вершины во float24 с усечением (железо PSP, ppsspp issue 12058), растеризация 12.4 «верх-лево»; камера за
машиной на дороге, 5 точек × 3 кадра. Щель — пиксель, который идеальная модель (float64) закрывает, а GE оставил пустым в
полосе до 2 пикселей между той же поверхностью (tools/seams_ge.py seams_of).
  без ключей                    — правило: центр клетки 40 м у всех её кусков (tools/psp_export.py cell_quant) и город в осях
                                  камеры (viewer/main.c): щелей 0 при склейке матриц (--ge cat) и по шагам (--ge sep) — код 0
  --rule piece --engine abs     — как до 03.10: свой центр у каждого куска, матрицы с переносом в сотни метров: при склейке
                                  матриц (cat) щели вдоль стыков кусков — обязан упасть (код 1)
Запуск: .venv/bin/python tests/seams/one_matrix.py [--rule cell|piece] [--engine rel|abs] [--ge cat|sep]"""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import seams_ge as G   # noqa: E402
import psp_export as E   # noqa: E402  (grid_quant, cell_quant, ORIGIN_STEP — правила экспортёра; диск при импорте не читается)

GRID, CELL = 2.0 ** -9, 40.0
X0, Z0 = 613.0917, 690.137


def road():
    """куски дороги: [(клетка 40 м, треугольники (n,3,3) в мире на решётке 2^-9 м)]; края кусков общие"""
    rng = np.random.default_rng(224)
    xs = np.r_[0, np.cumsum(rng.uniform(5, 11, 8))]; xs = xs[xs < 40]; xs = np.r_[xs, 40.0]
    zs = np.r_[0, np.cumsum(rng.uniform(5, 11, 40))]; zs = zs[zs < 200]; zs = np.r_[zs, 200.0]
    out = []
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            gx = np.linspace(xs[i], xs[i + 1], 4); gz = np.linspace(zs[j], zs[j + 1], 4); T = []
            for a in range(3):
                for b in range(3):
                    p = [(gx[a], gz[b]), (gx[a + 1], gz[b]), (gx[a + 1], gz[b + 1]), (gx[a], gz[b + 1])]
                    q = [np.round(np.array([X0 + x, 2.5 + 0.004 * (x + z), Z0 + z]) / GRID) * GRID for x, z in p]
                    T += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            T = np.array(T); c = T.reshape(-1, 3).mean(0)
            out.append(((int(np.floor(c[0] / CELL)), int(np.floor(c[2] / CELL))), T))
    return out


def pieces(rule):
    out = []
    for k, (cell, T) in enumerate(road()):
        P = T.reshape(-1, 3)
        if rule == 'piece': c, xyz, sc = E.grid_quant(P, GRID)
        else:
            cc = np.round(np.array([(cell[0] + .5) * CELL, 2.9, (cell[1] + .5) * CELL]) / E.ORIGIN_STEP) * E.ORIGIN_STEP
            c, xyz, sc, _ = E.cell_quant(P, cc, GRID)
        out.append(dict(i=k, lo=P.min(0), hi=P.max(0), fl=16 | 32, o=np.asarray(c, np.float32), sc=np.float32(sc),
                        qn=xyz.astype(np.float64).reshape(-1, 3, 3), qf=np.zeros((0, 3, 3))))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rule', default='cell', choices=('cell', 'piece'))
    ap.add_argument('--engine', default='rel', choices=('rel', 'abs')); ap.add_argument('--ge', default='cat', choices=('cat', 'sep'))
    a = ap.parse_args()
    L = G.lib(); P = pieces(a.rule); n = 0; frames = 0
    for t in np.linspace(20, 180, 5):
        for j in (0.0, 0.37, 0.74):
            car = np.array([X0 + 18.3, 2.5 + 0.004 * (18.3 + t + j) + .4, Z0 + t + j])
            eye, at = car + [0, 2.5, -5.5], car + [0, 1.4, 0]
            ref = G.frame(L, P, eye, at, 'ref', True, False); eng = G.frame(L, P, eye, at, a.ge, True, True, a.engine == 'rel')
            n += int(G.seams_of(ref, eng).sum()); frames += 1
    print(f'{"центр клетки у её кусков" if a.rule == "cell" else "свой центр у куска"}, движок {"в осях камеры" if a.engine == "rel" else "до правки"} '
          f'(GE {a.ge}): щелей {n} пикс. на {frames} кадрах, кусков {len(P)}')
    if n:
        print(f'FAIL: щели вдоль стыков кусков — {n} пикс.'); return 1
    print('PASS: стыки кусков закрыты'); return 0


if __name__ == '__main__':
    sys.exit(main())
