#!/usr/bin/env python3
"""Гейт №671 (Роб, 17.10): однострочный бабл задания с аватаром («TALK TO MARGE») стоит у верха текстовой области, как у PS2 и в панели типографики,
а не по центру рамки по высоте (регресс №640, viewer/ui.c BUBBLE_VCENTER1_OLD). Центр жёлтых пикселей текста по высоте в кадре 480x272 на трёх кадрах появления.
   b671_check.py НОВЫЙ_DIR ДО640_DIR  -> 0: центр нового = центру сборки до №640 (±1 px)
   b671_check.py --red СТАРЫЙ_DIR ДО640_DIR -> 0 только если старый (№640) отличается от до-№640 более чем на 3 px (красный контроль)"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
def cy(d):
    out = []
    for n in ('t2', 't3', 't4'):
        a = np.asarray(Image.open(Path(d) / f'{n}.png').convert('RGB')).astype(int)[185:250, 72:300]
        m = (a[..., 0] > 200) & (a[..., 1] > 200) & (a[..., 2] < 110)
        ys = np.nonzero(m)[0]
        if len(ys) < 20: sys.exit(f'FAIL: нет жёлтого текста на {n}')
        out.append(ys.mean() + 185)
    return float(np.mean(out))
red = sys.argv[1] == '--red'; args = sys.argv[2:] if red else sys.argv[1:]
c_new, c_ref = cy(args[0]), cy(args[1]); d = abs(c_new - c_ref)
print(f'центр текста: проверяемый {c_new:.1f}, до №640 {c_ref:.1f}, разница {d:.1f} px')
if red: sys.exit(0 if d > 3 else 1)
sys.exit(0 if d <= 1 else 1)
