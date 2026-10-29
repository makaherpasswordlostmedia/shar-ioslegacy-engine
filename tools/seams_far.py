#!/usr/bin/env python3
"""Правка Роба 106 «стыки рябят»: Т-стыки дальних версий кусков (дальше LOD_DIST 50 м, viewer/main.c) — сводка, не гейт.

    python tools/seams_far.py [build/level.shr]

tools/seams.py гейтит Т-стыки только ближней версии (экспорт режет их, tools/psp_export.py split_tjunctions, правка 37).
Дальняя версия — исходные треугольники диска (FAR_SPLIT 28 м, FAR_MIN 1.2 м²), разрез Т-стыков её не касается. Считаем:
  дальняя/дальняя — вершина дальней версии куска строго внутри ребра дальней версии другого куска (оба дальше 50 м);
  граница LOD     — вершина ближней версии куска внутри ребра дальней версии соседа: сосед уже дальний, этот ещё ближний
                    (нарезка 7/14 м даёт вершины в серединах рёбер). GE растеризует ребро и ломаную через вершину
                    по-разному (4 бита подпикселя) — вдоль шва искрит фон, как у правки 37. PPSSPP рисует с увеличением
                    и в плавающей точке — эту искру не показывает, проверка только геометрией и на PSP.
    python tools/seams_far.py LEVEL.shr --vs ALL.shr
  щели FAR_MIN — рёбра дальней версии LEVEL, у которых в ALL (тот же экспорт с SHR_FAR_MIN=0: все исходные треугольники)
                 второй треугольник есть, а в LEVEL выкинут (мельче FAR_MIN): открытый шов, м. Вершины города на общей
                 решётке (правка 37) — рёбра двух файлов совпадают бит в бит; стыки через Т-вершину не считаются (нижняя оценка)."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import shr7read, seams   # noqa: E402


def on_edges(Vd, Ed, tol=0.001, cell=2.0):
    """вершины Vd строго внутри рёбер Ed другого куска (как seams.tjunctions, без «иголок») -> (пар вершина×ребро, пар кусков)"""
    V = Vd['P'].reshape(-1, 3); VI = np.repeat(Vd['PI'], 3)
    _, inv = np.unique(np.c_[np.round(V / tol).astype(np.int64), VI], axis=0, return_index=True); V, VI = V[inv], VI[inv]
    kv = np.floor(V[:, [0, 2]] / cell).astype(np.int64); vkey = (kv[:, 0] + 100000) * 200000 + (kv[:, 1] + 100000)
    o = np.argsort(vkey, kind='stable'); vkey_s = vkey[o]
    P, PI = Ed['P'], Ed['PI']
    E0 = np.concatenate([P[:, 0], P[:, 1], P[:, 2]]); E1 = np.concatenate([P[:, 1], P[:, 2], P[:, 0]]); EI = np.tile(PI, 3)
    tot, pairs = 0, set()
    for c0 in range(0, len(E0), 100000):
        a, bb, ei = E0[c0:c0 + 100000], E1[c0:c0 + 100000], EI[c0:c0 + 100000]
        lo = np.floor((np.minimum(a, bb)[:, [0, 2]] - tol) / cell).astype(np.int64); hi = np.floor((np.maximum(a, bb)[:, [0, 2]] + tol) / cell).astype(np.int64)
        sp = hi - lo + 1; cnt = sp[:, 0] * sp[:, 1]
        rep = np.repeat(np.arange(len(a)), cnt); kk = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        key = (lo[rep, 0] + kk % sp[rep, 0] + 100000) * 200000 + (lo[rep, 1] + kk // sp[rep, 0] + 100000)
        s, t = np.searchsorted(vkey_s, key, 'left'), np.searchsorted(vkey_s, key, 'right'); m = t - s
        E = rep[np.repeat(np.arange(len(rep)), m)]; Vi = o[np.repeat(s, m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))]
        d_ = bb[E] - a[E]; l2 = (d_ * d_).sum(1); l2[l2 == 0] = 1e-18; tt = ((V[Vi] - a[E]) * d_).sum(1) / l2
        dist = np.linalg.norm(V[Vi] - (a[E] + tt[:, None] * d_), axis=1); Ln = np.sqrt(l2)
        hit = (dist < tol) & (tt * Ln > tol * 3) & ((1 - tt) * Ln > tol * 3) & (VI[Vi] != ei[E])
        tot += int(hit.sum()); pairs.update(zip(VI[Vi[hit]].tolist(), ei[E[hit]].tolist()))
    return tot, len(pairs)


def edges(d):
    """рёбра треугольников: ключи (две вершины на решётке, меньшая первой) и число треугольников на ребре"""
    P = np.round(d['P'] * 8192).astype(np.int64)   # решётка города 2^-9 м — целые в 1/8192 м без потерь
    a = np.concatenate([P[:, 0], P[:, 1], P[:, 2]]); b = np.concatenate([P[:, 1], P[:, 2], P[:, 0]])
    less = (a[:, 0] < b[:, 0]) | ((a[:, 0] == b[:, 0]) & ((a[:, 1] < b[:, 1]) | ((a[:, 1] == b[:, 1]) & (a[:, 2] < b[:, 2]))))
    lo, hi = np.where(less[:, None], a, b), np.where(less[:, None], b, a)
    k, cnt = np.unique(np.c_[lo, hi], axis=0, return_counts=True)
    return k, cnt


def open_len(d, dall):
    """длина рёбер, у которых в dall два треугольника и больше, а в d — один (второй выкинут)"""
    k1, c1 = edges(d); k2, c2 = edges(dall)
    v = np.concatenate([k1, k2]); tag = np.r_[np.zeros(len(k1), int), np.ones(len(k2), int)]
    cc = np.r_[c1, c2]
    _, inv = np.unique(v, axis=0, return_inverse=True); inv = inv.ravel()
    n1 = np.zeros(inv.max() + 1, int); n2 = np.zeros(inv.max() + 1, int); np.add.at(n1, inv[tag == 0], cc[tag == 0]); np.add.at(n2, inv[tag == 1], cc[tag == 1])
    first = np.full(inv.max() + 1, -1); first[inv[::-1]] = np.arange(len(inv))[::-1]
    opened = (n1 == 1) & (n2 >= 2)
    E = v[first[opened]] / 8192.0
    return float(np.linalg.norm(E[:, :3] - E[:, 3:], axis=1).sum()), int(opened.sum())


def main():
    shr = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'build/level.shr')
    if '--vs' in sys.argv:
        dall = shr7read.load(sys.argv[sys.argv.index('--vs') + 1], far=True); d = shr7read.load(shr, far=True)
        L, n = open_len(d, dall)
        print(f'{shr}: дальняя версия {len(d["P"]):,} треуг. (все исходные — {len(dall["P"]):,}); '
              f'щели FAR_MIN: {n:,} рёбер, {L:,.0f} м открытого шва')
        return 0
    dn, df = shr7read.load(shr), shr7read.load(shr, far=True)
    tn, tf = seams.tjunctions(dn), seams.tjunctions(df)
    lb = on_edges(dn, df)
    print(f'{shr}: ближняя версия {len(dn["P"]):,} треуг., Т-стыков между кусками {tn[0]:,} (гейт tools/seams.py)')
    print(f'  дальняя версия {len(df["P"]):,} треуг.: Т-стыков между кусками {tf[0]:,}, внутри куска {tf[1]:,}, «иголок» {tf[2]:,}')
    print(f'  граница LOD (ближняя вершина на дальнем ребре соседа): {lb[0]:,} точек, {lb[1]:,} пар кусков')
    return 0


if __name__ == '__main__':
    sys.exit(main())
