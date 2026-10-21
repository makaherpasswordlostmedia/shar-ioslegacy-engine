#!/usr/bin/env python3
"""Снимок модели машины с колёсами, поднятыми на dy (правка 354): сбоку, спереди-сбоку сверху и сверху — видно ли колесо
сквозь кузов. Программный z-буфер, без движка; кузов серый, колёса красные (видимая часть колеса = пробой, если она
лезет поверх крыла).
  .venv/bin/python tools/wheel_view.py МАШИНА OUT.png [--hide] [dy_перед dy_зад ...]   # несколько dy — ряды картинки
--hide — не рисовать колёса, которые не рисует оригинал (tools/wheel_clear.HIDDEN, как движок с правилом 354).
dy — подъём колеса по оси Y модели, м (как carvis.c jointXf). Перед — суставы колёс с z < 0 (модель смотрит в -Z)."""
import sys, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheel_clear as W

VIEWS = [('сбоку', (np.radians(-90), np.radians(0))), ('3/4 сверху', (np.radians(-35), np.radians(28))),
         ('сверху', (0.0, np.radians(89.9)))]
SZ = (300, 200)


def rot(yaw, pitch):
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]); Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rx @ Ry


def render(tris, cols, R, scale, ctr):
    img = np.full((SZ[1], SZ[0], 3), 235, np.uint8); zb = np.full((SZ[1], SZ[0]), -1e9)
    L = np.array([0.3, 0.8, 0.5]); L /= np.linalg.norm(L)
    for T, col in zip(tris, cols):
        P = (T - ctr) @ R.T
        n = np.cross(T[1] - T[0], T[2] - T[0]); nl = np.linalg.norm(n)
        if nl < 1e-12: continue
        sh = 0.45 + 0.55 * abs(np.dot(n / nl, L))
        u = P[:, 0] * scale + SZ[0] / 2; v = -P[:, 1] * scale + SZ[1] / 2; z = P[:, 2]
        x0, x1 = int(max(np.floor(u.min()), 0)), int(min(np.ceil(u.max()), SZ[0] - 1))
        y0, y1 = int(max(np.floor(v.min()), 0)), int(min(np.ceil(v.max()), SZ[1] - 1))
        if x0 > x1 or y0 > y1: continue
        d = (v[1] - v[2]) * (u[0] - u[2]) + (u[2] - u[1]) * (v[0] - v[2])
        if abs(d) < 1e-9: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        a = ((v[1] - v[2]) * (X - u[2]) + (u[2] - u[1]) * (Y - v[2])) / d
        b = ((v[2] - v[0]) * (X - u[2]) + (u[0] - u[2]) * (Y - v[2])) / d
        c = 1 - a - b; m = (a >= 0) & (b >= 0) & (c >= 0)
        Z = a * z[0] + b * z[1] + c * z[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= Z > sub
        sub[m] = Z[m]; img[y0:y1 + 1, x0:x1 + 1][m] = (np.array(col) * sh).astype(np.uint8)
    return img


def main():
    args = sys.argv[1:]; hide = '--hide' in args; args = [a for a in args if a != '--hide']
    car, out = args[0], args[1]
    dys = [float(x) for x in args[2:]] or [0.0]
    jpos, pieces, _, _ = W.car_mesh(W.CARS / f'{car}.p3d')
    mask = W.HIDDEN.get(car, 0) if hide else 0
    pieces = [(n, T) for n, T in pieces if not (re.fullmatch(r'w\d', n) and mask >> int(n[1]) & 1)]
    allP = np.concatenate([T.reshape(-1, 3) for _, T in pieces]); ctr = (allP.min(0) + allP.max(0)) / 2
    scale = 0.9 * SZ[0] / np.linalg.norm(allP.max(0) - allP.min(0))
    rows = []
    for i in range(0, len(dys), 2):
        dyf = dys[i]; dyr = dys[i + 1] if i + 1 < len(dys) else dyf
        tris, cols = [], []
        for n, T in pieces:
            wheel = re.fullmatch(r'w\d', n) is not None
            off = (dyf if jpos[n][2] < 0 else dyr) if wheel else 0.0
            for t in T: tris.append(t + np.array([0, off, 0])); cols.append((220, 40, 40) if wheel else (170, 170, 175))
        row = [render(tris, cols, rot(*a), scale, ctr) for _, a in VIEWS]
        im = Image.fromarray(np.concatenate(row, 1)); ImageDraw.Draw(im).text((4, 4), f'{car}  колёса +{dyf:.3f} / +{dyr:.3f} м' + ('  (скрытые оригиналом не рисуются)' if mask else ''), fill=(0, 0, 0))
        rows.append(np.asarray(im))
    Image.fromarray(np.concatenate(rows, 0)).save(out)
    print(out)


if __name__ == '__main__':
    main()
