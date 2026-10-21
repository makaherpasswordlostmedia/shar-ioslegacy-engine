#!/usr/bin/env python3
"""Compare ten post-Start seconds against the preserved PSP EBOOT capture.
Usage: python check.py REFERENCE_STAGE REFERENCE_SHOTS STAGE SHOTS
Real red: compile -DFE_START_INTRO_OLD=1; use four pre-title skip presses.
Default: five skips (intro restored before title); identical post-Start script.
"""
from pathlib import Path
import re
import sys
from PIL import Image, ImageChops, ImageStat
ref, refshots, run, shots = map(Path, sys.argv[1:])
errors = []
logs = [(p / 'smoke.txt').read_text() for p in (ref, run)]
for name, log in zip(('reference', 'candidate'), logs):
    if not re.search(r'^END$', log, re.M): errors.append(f'{name}: incomplete')
    if not re.search(r'SCRSHOT name=before_start .*show=PRESS_START', log): errors.append(f'{name}: title not captured')
    if not re.search(r'TITLE off key=0x8 ', log): errors.append(f'{name}: no Start exit')
    post = log.split('TITLE off key=0x8 ', 1)[-1]
    if re.search(r'INTROSHOT name=after_', post): errors.append(f'{name}: movie after Start')
for second in (1, 3, 5, 7, 9, 10):
    name = f'after_{second:02d}'
    for log in logs:
        if not re.search(rf'^SHOT {name} ', log, re.M): errors.append(f'missing {name}')
    a, b = [Image.open(p / (name + '.png')).convert('RGB') for p in (refshots, shots)]
    if a.size != (480,272) or b.size != a.size: errors.append(f'{name}: not native')
    # Whole living room, excluding display bezel. Allow animated gag/music phase;
    # measured good max 1.41; shipped regression min 69.05 (8-bit RGB MAE).
    mae = sum(ImageStat.Stat(ImageChops.difference(a,b).crop((25,40,455,230))).mean)/3
    print(f'{name}: RGB MAE={mae:.3f}, limit=5')
    if mae > 5: errors.append(f'{name}: different scene')
print('FAIL: ' + '; '.join(errors) if errors else 'PASS: title → Start → living room, six frames / ten seconds')
sys.exit(bool(errors))
