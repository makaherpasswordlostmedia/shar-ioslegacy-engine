#!/usr/bin/env python3
"""Helpers for the UI test EBOOT (tests/ui).

    python tests/ui/shots.py bg WINDOW.png OUT/bg.raw      # PPSSPP window shot of the level -> 480x272 RGBA raw
    python tests/ui/shots.py png DIR                        # DIR/shot_*.raw (480x272 RGBA, from the EBOOT) -> PNG

The window shot is cropped to the bottom 16:9 part (title bar on top) and reduced with a box
filter over the centre of each source cell, so an integer-scaled emulator window gives back the
480x272 frame.  The shot_*.raw files are exact GE frame dumps, no scaling involved.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 480, 272


def bg(src, out):
    im = np.asarray(Image.open(src).convert('RGBA'))
    h, w = im.shape[:2]
    k = w // W                                     # integer window scale (4 on a 2x retina window at 2x)
    frame = im[h - H * k:, :W * k]                 # PSP frame = bottom part, title bar above
    cells = frame.reshape(H, k, W, k, 4)
    c0, c1 = max(0, k // 2 - 1), k // 2 + 1        # centre of each cell (avoids filtered edges)
    small = cells[:, c0:c1, :, c0:c1].astype(np.float32).mean(axis=(1, 3))
    small[..., 3] = 255
    Path(out).write_bytes(np.round(small).astype(np.uint8).tobytes())
    Image.fromarray(np.round(small).astype(np.uint8), 'RGBA').save(str(out) + '.png')
    print('bg', src, '%dx%d scale %d ->' % (w, h, k), out)


def png(d):
    for f in sorted(Path(d).glob('shot_*.raw')):
        a = np.frombuffer(f.read_bytes(), np.uint8)
        if a.size != W * H * 4:
            print('skip', f, a.size); continue
        a = a.reshape(H, W, 4).copy(); a[..., 3] = 255
        Image.fromarray(a, 'RGBA').convert('RGB').save(f.with_suffix('.png'))
        print(f.with_suffix('.png'))


if __name__ == '__main__':
    if sys.argv[1] == 'bg':
        bg(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'png':
        png(sys.argv[2])
