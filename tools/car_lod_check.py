#!/usr/bin/env python3
"""Проверка дальней версии машин трафика (правка Роба 56, 29.09: «на машинах отваливаются текстуры: школьный автобус,
обычные серые машины»). Дальняя версия (дальше TR_LOD_DIST = 30 м, tools/traffic_export.py simplify_soup) должна
выглядеть как ближняя: рисунок текстуры на своих местах.

Мера — цвет текстуры в точках поверхности: точки дальней версии (решётка по площади треугольника) сравниваются с цветом
ближайшей точки ближней версии (та же решётка, поиск по ячейкам 15 см). Ошибка — средняя разница RGB (0…255) по площади
и доля точек с разницей > 64. Затенение (цвет вершин) не учитывается: только рисунок текстуры.
Дыры — доля площади ближней версии, у которой в 10 см нет поверхности дальней (корпус не должен разваливаться).

  python tools/car_lod_check.py              # все машины трафика уровня 1 + остов huskA -> OK / FAIL
  python tools/car_lod_check.py --old        # подброска: прежнее упрощение (сварка по позиции, UV старых углов) — обязано упасть
  python tools/car_lod_check.py --holes      # подброска: из дальней версии выкинут каждый 7-й треугольник — обязано упасть
  python tools/car_lod_check.py --level 2 --only schoolbu
Код выхода 0 = все модели в пределе, 1 = есть модель хуже предела."""
import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import traffic_export as te                  # noqa: E402
import psp_export as pe                      # noqa: E402

ERR_MAX = 8.0       # средняя разница RGB по площади, предел (замер 29.09: новое упрощение ≤ 5.3; прежнее — автобус 20, glastruc 11)
BAD_MAX = .05       # доля точек с разницей > 64 (новое ≤ 3.6 %, прежнее — автобус 14.5 %, glastruc 6.3 %)
HOLE_MAX = .03      # доля площади ближней версии без поверхности дальней в HOLE_D
HOLE_D = .10
CELL = .15


def simplify_old(P, UV, C, T, F, target):
    """прежнее упрощение (до правки 56): сварка по позиции, выжившие треугольники с UV/цветом своих старых углов"""
    import fast_simplification as fs
    key = np.round(P / 1e-3).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.reshape(-1)
    pts = np.zeros((len(uniq), 3)); np.add.at(pts, inv, P); pts /= np.bincount(inv)[:, None]
    tri = inv.reshape(-1, 3)
    good = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    idx = np.nonzero(good)[0]; tri = tri[good]
    if len(tri) <= target: return P, UV, C, T, F
    for red in np.linspace(1 - target / len(tri), .95, 12):
        _p, _t, coll = fs.simplify(pts, tri.astype(np.int32), target_reduction=float(red), return_collapses=True, agg=4)
        np_, nt_, mp = fs.replay_simplification(pts.astype(np.float32), tri.astype(np.int32), coll)
        rt = mp[tri]
        keep = (rt[:, 0] != rt[:, 1]) & (rt[:, 1] != rt[:, 2]) & (rt[:, 0] != rt[:, 2])
        srt = np.sort(rt, 1); _, first = np.unique(srt[keep], axis=0, return_index=True)
        sel = np.nonzero(keep)[0][np.sort(first)]
        if len(sel) <= target: break
    src = idx[sel]
    corners = (src[:, None] * 3 + np.arange(3)).reshape(-1)
    return np_[rt[sel]].reshape(-1, 3).astype(np.float32), UV[corners], C[corners], T[src], F[src]


def lattice(k):
    """барицентрическая решётка k x k (центры клеток нижнего треугольника)"""
    out = []
    for i in range(k):
        for j in range(k - i):
            a, b = (i + 1 / 3) / k, (j + 1 / 3) / k
            out.append((1 - a - b, a, b))
            if i + j < k - 1: out.append((1 - (i + 2 / 3) / k - (j + 2 / 3) / k, (i + 2 / 3) / k, (j + 2 / 3) / k))
    return np.array(out)


def samples(P, UV, T, texs, step=.06):
    """точки поверхности по площади -> (xyz, rgb, вес-площадь)"""
    tp, tu = P.reshape(-1, 3, 3).astype(np.float64), UV.reshape(-1, 3, 2).astype(np.float64)
    area = .5 * np.linalg.norm(np.cross(tp[:, 1] - tp[:, 0], tp[:, 2] - tp[:, 0]), axis=1)
    X, RGB, W = [], [], []
    for i in range(len(tp)):
        t = int(T[i])
        if t < 0 or t not in texs or area[i] < 1e-7: continue
        k = int(np.clip(np.ceil(np.sqrt(area[i] * 2) / step), 1, 24)); L = lattice(k)
        x = L @ tp[i]; uv = L @ tu[i]
        im = texs[t]; h, w = im.shape[:2]
        px = np.floor(uv[:, 0] * w).astype(int) % w; py = np.floor(uv[:, 1] * h).astype(int) % h
        X.append(x); RGB.append(im[py, px, :3]); W.append(np.full(len(L), area[i] / len(L)))
    return np.concatenate(X), np.concatenate(RGB).astype(np.float64), np.concatenate(W)


def nearest(xq, xr):
    """-> индекс ближайшей точки xr для каждой xq (-1 — нет в соседних ячейках) и расстояние"""
    cell = {}
    keys = np.floor(xr / CELL).astype(np.int64)
    for i, kk in enumerate(map(tuple, keys)): cell.setdefault(kk, []).append(i)
    cell = {k: np.array(v) for k, v in cell.items()}
    out = np.full(len(xq), -1); dist = np.full(len(xq), np.inf)
    off = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
    for i, kq in enumerate(np.floor(xq / CELL).astype(np.int64)):
        cand = [cell[(kq[0] + a, kq[1] + b, kq[2] + c)] for a, b, c in off if (kq[0] + a, kq[1] + b, kq[2] + c) in cell]
        if not cand: continue
        c = np.concatenate(cand); d = ((xr[c] - xq[i]) ** 2).sum(1)
        out[i] = c[d.argmin()]; dist[i] = float(np.sqrt(d.min()))
    return out, dist


def model(conv, name, cache, texblob, simplify, holes=False):
    p = te.GAME / 'art' / 'cars' / f'{name.lower()}.p3d'
    conv.export(p, 'lodchk_car', vehicle=True)
    meta = json.loads((te.OUT / 'lodchk_car.json').read_text()); raw = (te.OUT / 'lodchk_car.bin').read_bytes()
    for ext in ('json', 'bin'): (te.OUT / f'lodchk_car.{ext}').unlink()
    baked = pe.car_prims(meta, raw, cache, texblob, True)
    P = np.concatenate([b[3] for b in baked]); UV = np.concatenate([b[4] for b in baked]); C = np.concatenate([b[5] for b in baked])
    T = np.concatenate([np.full(len(b[3]) // 3, b[1]) for b in baked]); Fl = np.concatenate([np.full(len(b[3]) // 3, b[2]) for b in baked])
    ntri = len(P) // 3
    if ntri <= te.LOD_TRIS: return dict(name=name, tris=ntri, lod=ntri, err=0.0, bad=0.0, hole=0.0, same=True)
    sP, sUV, sC, sT, sF = simplify(P, UV, C, T, Fl, te.LOD_TARGET)
    if holes:
        k = np.arange(len(sP) // 3) % 7 != 3; kk = np.repeat(k, 3)
        sP, sUV, sC, sT, sF = sP[kk], sUV[kk], sC[kk], sT[k], sF[k]
    url = {v: k for k, v in cache.items()}
    texs = {t: np.asarray(Image.open(pe.ASSETS / url[t].split('#')[0]).convert('RGBA'), np.uint8) for t in set(T.tolist()) if t >= 0}
    xr, rgbr, wr = samples(P, UV, T, texs)
    xq, rgbq, wq = samples(sP, sUV, sT, texs)
    j, _ = nearest(xq, xr); ok = j >= 0
    diff = np.abs(rgbq[ok] - rgbr[j[ok]]).mean(1); w = wq[ok]
    _, dr = nearest(xr, xq)
    return dict(name=name, tris=ntri, lod=len(sP) // 3, err=float((diff * w).sum() / w.sum()),
                bad=float(w[diff > 64].sum() / w.sum()), hole=float(wr[dr > HOLE_D].sum() / wr.sum()), same=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--old', action='store_true')
    ap.add_argument('--only', default=''); ap.add_argument('--holes', action='store_true')
    a = ap.parse_args()
    traffic, _ = te.level_script(a.level)
    names = [t[0] for t in traffic] + ['huskA']
    if a.only: names = [n for n in names if n.lower() in a.only.lower().split(',')]
    conv = te.Converter(); cache = {}; texblob = []
    simplify = simplify_old if a.old else te.simplify_soup
    fails = []
    tag = 'прежнее упрощение — подброска' if a.old else 'текущее упрощение' + (', выкинут каждый 7-й треугольник — подброска' if a.holes else '')
    print(f'дальняя версия машин ({tag}), предел: ошибка ≤ {ERR_MAX}, доля > 64 ≤ {BAD_MAX:.0%}, дыры ≤ {HOLE_MAX:.0%}')
    for n in names:
        r = model(conv, n, cache, texblob, simplify, a.holes)
        bad = r['err'] > ERR_MAX or r['bad'] > BAD_MAX or r['hole'] > HOLE_MAX
        if bad: fails.append(n)
        print(f'  {"FAIL" if bad else "ok  "} {n:10s} {r["tris"]:5d} -> {r["lod"]:4d} треуг.  ошибка {r["err"]:5.1f}  '
              f'доля > 64: {r["bad"]:5.1%}  дыры {r["hole"]:5.1%}' + ('  (без упрощения)' if r['same'] else ''))
    if fails:
        print('FAIL: дальняя версия рвёт рисунок или корпус: ' + ', '.join(fails)); sys.exit(1)
    print(f'OK: дальняя версия {len(names)} моделей держит рисунок')


if __name__ == '__main__':
    main()
