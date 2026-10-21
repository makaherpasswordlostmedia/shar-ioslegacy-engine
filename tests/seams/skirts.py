#!/usr/bin/env python3
"""Правка Роба 106 (повтор 01.10): юбки швов tools/skirts.py на заведомом случае, без диска — растеризатором кадра PSP
tools/seams_raster.py (12.4, «верх-лево», ближняя плоскость режет).

Сцена: дорога вдоль z из двух кусков A (x < 0) и B (x > 0.3). Между ними полоса 0.3 м (бордюр/кромка): в ближней версии
куска B она есть, в дальней — выкинута (мелочь мельче FAR_MIN): щель в дальней версии. Камера на 6 м над дорогой, в 70 м
от начала, куски дальше 50 м — рисуются дальними версиями. Рядом кусок C с ребром-близнецом у A (край закрыт: юбки быть не
должно) и кусок D над обрывом (за краем пусто: юбки нет).
  без ключа      — юбки по правилу: дыр в кадре 0, юбок у закрытого края и у обрыва нет (код 0)
  --rule none    — без юбок: щель видна — обязан упасть (код 1)
  --rule notwin  — юбки на всех краях земли, без проверки близнеца: лишние юбки у C — обязан упасть (код 1)
Запуск: .venv/bin/python tests/seams/skirts.py [--rule none|notwin]"""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import skirts, seams_raster as S   # noqa: E402

VT = np.dtype([('u', '<f4'), ('v', '<f4'), ('c', '<u4'), ('x', '<f4'), ('y', '<f4'), ('z', '<f4')])


def quads(x0, x1, z0, z1, y=0.0, step=8.0):
    """полоса земли квадами по z (шаг step) -> (n,3,3), обход одинаковый"""
    T = []
    z = z0
    while z < z1 - 1e-9:
        z2 = min(z + step, z1)
        a, b, c, d = (x0, y, z), (x1, y, z), (x1, y, z2), (x0, y, z2)
        T += [(a, b, c), (a, c, d)]; z = z2
    return np.array(T, np.float64)


def scene():
    A = quads(-12, 0, 0, 160)
    sliver = quads(0, 0.3, 0, 160)
    B = quads(0.3, 12, 0, 160)
    C = quads(-24, -12, 0, 160)                        # ребро x = -12 общее с A (близнец)
    D = quads(30, 40, 0, 160, y=5.0)                    # плато над обрывом: за краем x = 30 земли нет
    # (флаги, ближняя, дальняя): у B ближняя с полосой, дальняя — без
    return [(0, A, A), (0, np.concatenate([sliver, B]), B), (0, C, C), (0, D, D)]


def soup(T):
    v = np.zeros(len(T) * 3, VT); P = T.reshape(-1, 3)
    v['x'], v['y'], v['z'] = P[:, 0], P[:, 1], P[:, 2]; v['c'] = 0xFFFFFFFF
    return v


def apply(pcs, rule):
    if rule == 'none': return pcs, {}
    if rule == 'notwin':   # все края земли, будто близнецов нет
        orig = skirts.EdgeOwners.twin
        skirts.EdgeOwners.twin = lambda self, K, own: np.zeros(len(K), bool)
    plan, _ = skirts.plan(pcs)
    if rule == 'notwin': skirts.EdgeOwners.twin = orig
    out = []
    for i, (fl, Tn, Tf) in enumerate(pcs):
        r = [Tn, Tf]
        if i in plan:
            for v in (0, 1):
                sv = skirts.skirt_soup(soup(r[v]), *plan[i][v])
                r[v] = np.concatenate([r[v], np.stack([sv['x'], sv['y'], sv['z']], 1).reshape(-1, 3, 3)])
        out.append((fl, r[0], r[1]))
    return out, plan


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rule', default='skirt'); a = ap.parse_args()
    pcs, plan = apply(scene(), a.rule)
    pieces = []
    for fl, Tn, Tf in pcs:
        allp = np.concatenate([Tn, Tf]).reshape(-1, 3)
        pieces.append((allp.min(0), allp.max(0), fl, Tn.astype(np.float32), Tf.astype(np.float32), 0))
    L = S.lib(); holes = 0
    for x in (-0.5, 0.15, 0.8):   # камера вдоль щели, чуть левее, над ней, правее
        cov, dep, gb = S.frame(L, pieces, np.array([x, 6.0, -70.0]), np.array([x, 0.0, 90.0]))
        holes += int(S.on_ground(S.thin_holes(cov) | S.through(cov, dep), cov & gb).sum())
    nC = sum(len(plan.get(2, ((), ()))[v][0]) for v in (0, 1)) if plan else 0
    nD = sum(len(plan.get(3, ((), ()))[v][0]) for v in (0, 1)) if plan else 0
    nAB = sum(len(plan.get(i, ((), ()))[1][0]) for i in (0, 1)) if plan else 0
    ok = holes == 0 and nC == 0 and nD == 0 and nAB > 0
    print(f'{"OK" if ok else "FAIL"} ({a.rule}): швов на дороге в 3 кадрах {holes}, юбок дальних версий у щели A|B {nAB}, '
          f'у закрытого края C {nC}, у обрыва D {nD}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
