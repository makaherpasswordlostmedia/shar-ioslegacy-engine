#!/usr/bin/env python3
"""Правка Роба 106: правило дальних версий (tools/psp_export.py far_keep) на заведомом случае, без диска.
Дорога и тротуар — крупные грани, между ними бордюр 0.15 м из мелких граней (узкая полоса мала по площади), рёбра общие;
над тротуаром отдельная мелочь (ящик без общих рёбер). Шов открыт, если ребро общее у оставленной и выкинутой граней.
  --rule area  — правило до правки: бордюр выкинут, шов 10 м — обязан упасть (код 1)
  без ключа    — правило швов: шов 0, мелочь выкинута (код 0);  --grow 0 — предел роста 0: шов снова открыт (код 1)
Запуск: .venv/bin/python tests/seams/far_keep.py [--rule area|seam] [--grow 0.15]"""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def load_rule(rule, grow):
    """tri_area + far_keep из экспортёра без его тяжёлых импортов (диск, текстуры)"""
    src = (ROOT / 'tools/psp_export.py').read_text(encoding='utf-8')
    i, j = src.index('def tri_area(P):'), src.index('def gradient_rows(url):')
    ns = {'np': np, 'FAR_MIN': 1.2, 'FAR_RULE': rule, 'FAR_GROW': grow}
    exec(src[i:j], ns)
    return ns['far_keep']


def quad(a, b, c, d): return [a, b, c, a, c, d]


def scene():
    road, side, curb = [], [], []
    for x in range(0, 10, 2):   # полосы по 2 м: вершины бордюра — общие с дорогой и тротуаром (как после разреза Т-стыков)
        road += quad((x, 0, 0), (x + 2, 0, 0), (x + 2, 0, 10), (x, 0, 10))              # 10 м² на грань
        curb += quad((x, 0, 10), (x + 2, 0, 10), (x + 2, .15, 10), (x, .15, 10))        # 0.15 м²
        side += quad((x, .15, 10), (x + 2, .15, 10), (x + 2, .15, 13), (x, .15, 13))    # 3 м²
    box = quad((5, .3, 11), (5.3, .3, 11), (5.3, .6, 11), (5, .6, 11))                  # мелочь, своих рёбер
    plaza = sum((quad((x, 0, 50), (x + 3, 0, 50), (x + 3, 0, 53), (x, 0, 53)) for x in range(0, 90, 3)), [])   # 60 крупных
    # поодаль: предел роста 15 % от 80 крупных = 12 граней, бордюр (10) в него входит
    return [(k, 0, np.array(v, np.float32), None, None) for k, v in enumerate((road, side, curb, box, plaza))]


def open_seams(prims, masks):
    P = np.concatenate([p[2].reshape(-1, 3, 3) for p in prims]); keep = np.concatenate(masks); E = {}
    for t, tri in enumerate(P):
        for i in range(3):
            e = tuple(sorted((tuple(np.round(tri[i], 3)), tuple(np.round(tri[(i + 1) % 3], 3)))))
            E.setdefault(e, []).append(t)
    return sum(float(np.linalg.norm(np.subtract(*e))) for e, ts in E.items()
               if any(keep[t] for t in ts) and not all(keep[t] for t in ts)), int(keep.sum()), len(keep)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rule', default='seam'); ap.add_argument('--grow', type=float, default=.15)
    a = ap.parse_args()
    prims = scene(); masks, msg = load_rule(a.rule, a.grow)(prims)
    L, kept, n = open_seams(prims, masks); box = bool(masks[3].any())
    ok = L == 0 and not box
    print(msg)
    print(f'{"OK" if ok else "FAIL"} ({a.rule}, рост {a.grow:g}): открытых швов {L:.2f} м, оставлено {kept} из {n} граней, '
          f'отдельная мелочь {"оставлена" if box else "выкинута"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
