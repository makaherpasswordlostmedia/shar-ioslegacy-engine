#!/usr/bin/env python3
# №953: чёрные заливки и трещины на дыме. Маска дыма = отличие кадра от кадра без дыма (ref: та же машина, урон 0, камера стоит); считаем тёмные пиксели
# (max канал < 30), которых на фоне не было (фон светлее 70), в столбе дыма над капотом (без шкалы HUD и самой машины). Замер 25.10: вырезка 190, мягкий дым 9. Вырезка (flag smoke953 0) даёт чёрную кайму и трещины между клубами, мягкий дым (1) — нет. Выход 0 — ПРОВАЛ не найден.
#   check.py ПАПКА old|new  -> печатает замер, последняя строка OK/BAD
import sys
from PIL import Image
import numpy as np
d, kind = sys.argv[1], sys.argv[2]
ref = np.asarray(Image.open(d + '/ref.png').convert('RGB')).astype(int)[66:128, 140:340]
tot = 0; mask_tot = 0
for i in range(4):
    a = np.asarray(Image.open('%s/%s%d.png' % (d, 'o' if kind == 'old' else 'n', i)).convert('RGB')).astype(int)[66:128, 140:340]
    m = np.abs(a - ref).max(axis=2) > 24
    dark = m & (a.max(axis=2) < 30) & (ref.max(axis=2) > 70)
    tot += int(dark.sum()); mask_tot += int(m.sum())
print('замер %s: тёмных (<30) пикселей внутри дыма %d из %d' % (kind, tot, mask_tot))
ok = tot <= 40
print('OK' if ok else 'BAD'); sys.exit(0 if ok else 1)
