#!/usr/bin/env python3
"""Средняя яркость кадров (0–255, без нижних 16 строк подписи смоука): tools/luma.py a.png b.png ..."""
import sys
from PIL import Image, ImageStat
for p in sys.argv[1:]:
    im = Image.open(p).convert('L'); w, h = im.size
    print(f"{p.split('/')[-1]}: {ImageStat.Stat(im.crop((0, 0, w, h - 16 if w < 600 else h))).mean[0]:.1f}")
