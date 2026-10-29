#!/usr/bin/env python3
"""Числовая проверка карточки-ориентира против настоящей геометрии (шов проявления). Карточка стоит на луче камера-башня и масштабируется равномерно от глаза, поэтому
её угловое положение и размер совпадают с настоящей башней по построению; остаётся различие ПРОФИЛЯ: карточка симметрична по оси (макс. радиус на каждый метр высоты),
настоящая башня может быть несимметрична и квантована до 0,01 м. Скрипт берёт horizon.shr + level.shr, для азимутов обзора считает по высотам: на сколько карточка шире (лишнее) или уже настоящей
стороны башни в метрах и в пикселях экрана (480x272, FOVY 48,8 и 55) на дистанциях 235..265 м.
  horizon_lm_check.py LEVEL.shr horizon.shr [--lm 0]"""
import sys, struct, argparse
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('hor'); ap.add_argument('--lm', type=int, default=0); ap.add_argument('--r', type=float, default=16.)
    a = ap.parse_args()
    b = Path(a.hor).read_bytes(); nl, lo = struct.unpack_from('<II', b, 12)
    cx, cz, y0, H, npts, off = struct.unpack_from('<4fII', b, lo + 32 * a.lm)
    prof = np.array([struct.unpack_from('<HH', b, off + 4 * k) for k in range(npts)], float) / 100.   # (радиус, высота)
    d = shr7read.load(a.level, far=False, owner=0); keep = (d['FL'] & 7) == 0
    V = d['P'][keep].reshape(-1, 3)
    m = np.hypot(V[:, 0] - cx, V[:, 2] - cz) < a.r; W = V[m]; W = W[W[:, 1] >= y0]
    hb = np.arange(0, int(H) + 1)
    card = np.interp(hb, prof[:, 1], prof[:, 0])
    worst_extra = worst_miss = 0.
    for az in np.arange(0, 360, 15):
        t = np.radians(az); rv = np.array([np.cos(t), np.sin(t)])   # правый вектор взгляда на ось
        p = (W[:, 0] - cx) * rv[0] + (W[:, 2] - cz) * rv[1]; h = W[:, 1] - y0
        for i in hb:
            s = (h >= i) & (h < i + 1)
            if s.sum() < 6 or p[s].max() <= 0 or p[s].min() >= 0: continue   # только высоты, где есть вершины по обе стороны оси (иначе сторона неизвестна)
            real = max(p[s].max(), -p[s].min())   # большая из двух сторон (карточка симметрична)
            realmin = min(p[s].max(), -p[s].min())
            worst_extra = max(worst_extra, card[i] - realmin)   # карточка шире узкой стороны
            worst_miss = max(worst_miss, real - card[i])        # карточка уже широкой стороны
    print('башня: высота %.1f м, профиль %d точек, радиусов в сантиметрах; точек геометрии %d' % (H, npts, len(W)))
    print('карточка шире реальной узкой стороны не более %.2f м; уже реальной широкой стороны не более %.2f м' % (worst_extra, worst_miss))
    for fov in (48.8, 55.0):
        for D in (235, 265):
            ppm = 272 / (2 * np.tan(np.radians(fov / 2)) * D)
            print('FOVY %.1f, %d м: %.2f пикс/м -> лишнее %.1f пикс, недобор %.1f пикс' % (fov, D, ppm, worst_extra * ppm, worst_miss * ppm))
    return 0


if __name__ == '__main__':
    sys.exit(main())
