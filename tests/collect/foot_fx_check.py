#!/usr/bin/env python3
"""Headless paired shots: extra saturated source flash pixels must be present.
The identical OLD pictures are a red control for the image checker itself.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
green, red = map(Path, sys.argv[1:3])
assert 'COLLEV wasp_zap' in (green/'smoke.txt').read_text()
for shot in ['kick', 'zap']:
    a = np.asarray(Image.open(green/(shot+'.png')).convert('RGB'))
    b = np.asarray(Image.open(red/(shot+'.png')).convert('RGB'))
    # Exclude radar/counters; source flashes saturate all three channels.
    white_a = np.all(a[40:200, 100:340] == 255, axis=2)
    white_b = np.all(b[40:200, 100:340] == 255, axis=2)
    extra = int((white_a & ~white_b).sum())
    assert extra > 0, f'{shot}: no authored flash against OLD'
    print(f'PASS {shot}: {extra} extra white source pixels')
