#!/usr/bin/env python3
"""Ключ-спрайт (№803): кадры оборота настоящей 3D-модели ключа без Blender — свой растеризатор (у Blender картинка ключа ложилась пятнами: проверено
программной отрисовкой той же раскладки UV — у диска она верная). Вход — tools/wrench/wrench_dump.py (coin.json, coin_tex.png), выход — f_NN.png
с прозрачным фоном для tools/coin/coin_pack.py.
    python3 tools/wrench/wrench_raster.py SRC_DIR OUT_DIR [N=32] [RES=128] [SS=2]   (№829: ключ — RES 128, SS 4, coin_pack.py --px 128 --page --soft)
Ортографическая камера спереди, поворот вокруг вертикали через центр рамки модели (как coin_blender.py), масштаб — больший размер рамки × 1,08;
свет: рассеянный 0,45 + направленный сверху-слева-спереди 0,65 (ключ в игре не металл с отражениями — простая заливка), сглаживание 2×2."""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image

def raster(Xr, UV, C, T, texs, TX, S, RES, lit_on=True, cut=None, ss=2):
    """Один кадр: вершины Xr уже в осях камеры (x вправо, y вверх, z к зрителю), ортомасштаб S м на кадр RES пикс, сглаживание 2×2.
    texs — картинки RGBA 0..1, TX — номер картинки треугольника, cut — треугольники с вырезкой по альфе картинки (> 0,25, как альфа-тест GE).
    UV повторяются (GU_REPEAT). lit_on=False — без света (значки msnart рисуются без освещения: цвет вершин × картинка)."""
    SS = ss; R = RES * SS   # сглаживание SS × SS отсчётов на пиксель: край — доля покрытия (мягкая альфа)
    L = np.array([-0.4, 0.6, 0.7]); L /= np.linalg.norm(L)
    px = (Xr[:, 0] / S + .5) * R; py = (.5 - Xr[:, 1] / S) * R; pz = Xr[:, 2]
    col = np.zeros((R, R, 3)); al = np.zeros((R, R)); zb = np.full((R, R), -1e9)
    for ti, t in enumerate(T):
        x0, y0, x1, y1, x2, y2 = px[t[0]], py[t[0]], px[t[1]], py[t[1]], px[t[2]], py[t[2]]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9: continue
        bx0, bx1 = max(int(math.floor(min(x0, x1, x2))), 0), min(int(math.ceil(max(x0, x1, x2))), R - 1)
        by0, by1 = max(int(math.floor(min(y0, y1, y2))), 0), min(int(math.ceil(max(y0, y1, y2))), R - 1)
        if bx0 > bx1 or by0 > by1: continue
        gx, gy = np.meshgrid(np.arange(bx0, bx1 + 1) + .5, np.arange(by0, by1 + 1) + .5)
        w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / den; w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / den; w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any(): continue
        z = w0 * pz[t[0]] + w1 * pz[t[1]] + w2 * pz[t[2]]
        sub = zb[by0:by1 + 1, bx0:bx1 + 1]; m &= z > sub
        if not m.any(): continue
        tex = texs[TX[ti] if TX is not None else 0]; TH, TW = tex.shape[:2]
        u = w0 * UV[t[0], 0] + w1 * UV[t[1], 0] + w2 * UV[t[2], 0]; v = w0 * UV[t[0], 1] + w1 * UV[t[1], 1] + w2 * UV[t[2], 1]
        tc = tex[np.floor(v * TH).astype(int) % TH, np.floor(u * TW).astype(int) % TW]
        if cut is not None and cut[ti]: m &= tc[..., 3] > .25
        if not m.any(): continue
        vc = w0[..., None] * C[t[0]] + w1[..., None] * C[t[1]] + w2[..., None] * C[t[2]]
        if lit_on:
            n = np.cross(Xr[t[1]] - Xr[t[0]], Xr[t[2]] - Xr[t[0]]); n /= (np.linalg.norm(n) + 1e-12)
            c = np.clip(tc[..., :3] * vc * (.45 + .65 * abs(float(n @ L))) * 1.15, 0, 1)   # обе стороны: у модели нет задних граней «изнутри»
        else:
            c = np.clip(tc[..., :3] * vc, 0, 1)
        sub[m] = z[m]; col[by0:by1 + 1, bx0:bx1 + 1][m] = c[m]; al[by0:by1 + 1, bx0:bx1 + 1][m] = 1.0
    img = np.concatenate([col, al[..., None]], 2).reshape(RES, SS, RES, SS, 4).mean((1, 3))
    rgb = np.where(img[..., 3:4] > 0, img[..., :3] / np.maximum(img[..., 3:4], 1e-6), 0)
    return Image.fromarray(np.concatenate([rgb, img[..., 3:4]], 2).__mul__(255).round().astype(np.uint8), 'RGBA')

def main(src, out, N=32, RES=128, SS=2):
    src, out = Path(src), Path(out); out.mkdir(parents=True, exist_ok=True)
    d = json.loads((src / 'coin.json').read_text())
    P = np.array(d['P'], np.float64); UV = np.array(d['UV'], np.float64); C = np.array(d['C'], np.float64)[:, :3]; T = np.array(d['T'], np.int64)
    UV[:, 1] = 1.0 - UV[:, 1]   # в coin.json v перевёрнут под Blender — вернуть v от верха картинки
    texs = [np.asarray(Image.open(src / 'coin_tex.png').convert('RGBA'), np.float64) / 255.0]
    lo, hi = P.min(0), P.max(0); cen = (lo + hi) / 2; S = max(hi[0] - lo[0], hi[1] - lo[1]) * 1.08
    for k in range(N):
        a = 2 * math.pi * k / N; ca, sa = math.cos(a), math.sin(a)
        X = P - cen; Xr = np.c_[X[:, 0] * ca + X[:, 2] * sa, X[:, 1], -X[:, 0] * sa + X[:, 2] * ca]
        raster(Xr, UV, C, T, texs, None, S, RES, ss=SS).save(out / f'f_{k:02d}.png')
    print('WRENCHRASTER', N, 'кадров', RES, 'px; ортомасштаб', round(S, 4), 'центр', [round(x, 4) for x in cen])

if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[1], int(a[2]) if len(a) > 2 else 32, int(a[3]) if len(a) > 3 else 128, int(a[4]) if len(a) > 4 else 2)
