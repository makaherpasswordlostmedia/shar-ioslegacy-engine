"""Compare two L4 lamp views and the L5 scene across the real OLD flag."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
root = Path(sys.argv[1])
for name, new, old in [('control4a','control','control-old'), ('control4b','control','control-old'), ('control5','control5','control5-old')]:
    a = np.asarray(Image.open(root/f'{new}-shots/{name}.png'),dtype=float)
    b = np.asarray(Image.open(root/f'{old}-shots/{name}.png'),dtype=float)
    error = float(np.abs(a-b).mean())
    changed = int(np.any(a!=b,axis=2).sum())
    print(name, 'MAE', error, 'changed pixels', changed)
    assert error < .01 and changed <= 16, 'neighbor scene changed'
print('PASS: neighboring lamp/glow scenes')
