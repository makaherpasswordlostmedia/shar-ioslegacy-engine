#!/usr/bin/env python3
"""№889 (Роб 23.10: «текст пунктов главного меню после увеличения рваный по пикселям; размер как в Options (Sound/Camera/Game/Picture), там чёткий; расстановку оставить»).
По кадрам f0..f5 прогона tests/menu889/scenario.txt (желтое слово выбранного пункта):
  1. слово не меняет размер от кадра к кадру (пульс масштабом пересэмплировал буквы каждый кадр: ширина гуляла на ~15 px) — разброс ширины и высоты ≤ 1 px;
  2. высота букв как у Options паузы (заглавная boulder_16 x2 = 12 px, ±1; было 16 px у boulder_24 x1,5756);
  3. центр слова по x — в середине между стрелками (±3 px), по y не уехал выше 25 / ниже 60 (расстановка прежняя).
  check.py RUN_DIR [--expect-fail]   0 = PASS; --expect-fail: 0 только если упало (зелёный с №924: сборка -DMENU_PULSE924_OLD=1 — пульс снят; красный: обычная сборка №924 с пульсом / прежний пакет)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
CAP = 12


def ink(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)[20:66, 90:390]
    m = (a[..., 0] > 225) & (a[..., 1] > 190) & (a[..., 2] < 70)
    ys, xs = np.nonzero(m)
    return None if len(xs) < 40 else (int(xs.min()) + 90, int(xs.max()) + 90, int(ys.min()) + 20, int(ys.max()) + 20)


def main():
    run = Path(sys.argv[1]); errs = []
    F = [ink(run / f'f{i}.png') for i in range(6)]
    if any(f is None for f in F): errs.append('слово пункта не найдено на кадрах')
    else:
        w = [f[1] - f[0] + 1 for f in F]; h = [f[3] - f[2] + 1 for f in F]
        cx = [(f[0] + f[1]) / 2 for f in F]; cy = [(f[2] + f[3]) / 2 for f in F]
        print(f'  ширина {min(w)}..{max(w)} px, высота {min(h)}..{max(h)} px (заглавная Options {CAP}), центр x {min(cx):.1f}..{max(cx):.1f}, y {min(cy):.1f}..{max(cy):.1f}')
        if max(w) - min(w) > 1 or max(h) - min(h) > 1: errs.append(f'размер гуляет: ширина {min(w)}..{max(w)}, высота {min(h)}..{max(h)} (пульс пересэмплирует буквы)')
        if abs(float(np.median(h)) - CAP) > 1.5: errs.append(f'высота букв {np.median(h):.0f} px, как у Options — {CAP}')
        if abs(float(np.median(cx)) - 240) > 20: errs.append(f'слово не по центру: x {np.median(cx):.0f}')
        if not 25 <= float(np.median(cy)) <= 60: errs.append(f'слово уехало по вертикали: y {np.median(cy):.0f}')
    ok = not errs
    for e in errs: print('  FAIL', e)
    print(('PASS' if ok else 'FAIL') + f' · tests/menu889/check.py {run.name}')
    return (0 if not ok else 1) if '--expect-fail' in sys.argv else (0 if ok else 1)


if __name__ == '__main__':
    sys.exit(main())
