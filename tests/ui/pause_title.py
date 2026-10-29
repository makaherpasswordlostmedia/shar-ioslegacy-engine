#!/usr/bin/env python3
"""Заголовок паузы «PAUSE MENU» на снимке окна эмулятора (tools/ui_anim_gate.sh, снимок pause_title): замер по пикселям.
   pause_title.py SHOT.png [--board-top 40] -> код 0 = крупно и ровно посередине полосы над рамкой
Ожидание (tools/ui_export.py pause_title_face): заглавные ~половина полосы SAFE_Y..верх рамки (34 px -> 17 px), крупнее
пунктов (заглавная пункта 10 px), середина букв — посередине полосы (±2 px), до рамки не достаёт."""
import argparse
import sys

import numpy as np
from PIL import Image

W, H, SAFE_Y = 480, 272, 6
ap = argparse.ArgumentParser()
ap.add_argument('shot')
ap.add_argument('--board-top', type=int, default=40)
a = ap.parse_args()
im = np.asarray(Image.open(a.shot).convert('RGB')).astype(int)
k = im.shape[1] // W
fr = im[im.shape[0] - H * k:, :W * k]
psp = fr.reshape(H, k, W, k, 3)[:, k // 2, :, k // 2]          # центр каждой клетки окна (целый масштаб)
band = psp[:a.board_top, 100:380]
white = (band.min(axis=2) >= 215)
rows = np.where(white.sum(1) >= 3)[0]
if not len(rows):
    print('pause title: КРАСНОЕ — над рамкой нет белого текста'); sys.exit(1)
top, bot = int(rows[0]), int(rows[-1])
cap = bot - top + 1; mid = (top + bot + 1) / 2; want = (SAFE_Y + a.board_top) / 2
cols = np.where(white.any(0))[0]; cx = 100 + (cols[0] + cols[-1] + 1) / 2
checks = [(cap >= 15, 'высота букв %d px (>= 15; пункт меню — 10, прежний заголовок — 7)' % cap),
          (abs(mid - want) <= 2, 'середина букв y=%.1f, середина полосы %.1f (±2)' % (mid, want)),
          (bot <= a.board_top - 3, 'низ букв y=%d, верх рамки %d (зазор >= 3)' % (bot, a.board_top)),
          (abs(cx - W / 2) <= 3, 'по центру экрана: x=%.1f (240 ±3)' % cx)]
ok = all(c for c, _ in checks)
print('pause title: %s' % ('OK' if ok else 'КРАСНОЕ'))
for c, m in checks:
    print('  %s %s' % ('OK  ' if c else 'FAIL', m))
sys.exit(0 if ok else 1)
