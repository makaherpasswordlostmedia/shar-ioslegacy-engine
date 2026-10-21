"""Native F14-2: black corners must preserve the separately rendered background.
Usage: pixels.py SHOTS BACKGROUND_SHOTS; actual GLOW_BLEND_OLD must fail.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
p, ref = map(Path, sys.argv[1:])
a = np.asarray(Image.open(p/'field.png'), dtype=float)
b = np.asarray(Image.open(ref/'field.png'), dtype=float)
# Fixed lower corner of the authored glow64 quad, away from the HUD/player/glow core.
a, b = a[225:265, 285:355], b[225:265, 285:355]
error = float(np.abs(a-b).mean())
lost = float(np.maximum(b-a, 0).mean())
print(f'corner background MAE={error:.3f}, darkening={lost:.3f}')
# GE blends into RGB565: permit one destination quantization step per channel.
qa = np.rint(a * np.array([31, 63, 31]) / 255)
qb = np.rint(b * np.array([31, 63, 31]) / 255)
steps = float(np.abs(qa-qb).max())
print(f'max RGB565 code difference={steps}')
assert steps <= 1, 'opaque black glow corner'
print('PASS')
