#!/usr/bin/env python3
"""Compare real loading-screen captures with the native two-frame fire animation.

Usage: fuse_frames.py capture-directory capture-directory [--red]
--red holds frame zero in the reference: a capture of frame one must reject it.
Reads SCRSHOT's actual screen clock/progress, masks to the flame, keeps the
changing star background at the same time. No PSP acceptance claim.
"""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import load_export as L

out = ROOT / 'build/codex-terminal/rob-pack/385'
res = L.export('load', out / 'fuse-test.shr', mocks=False)
fire = next(t for t in res['screens']['loading'] if t['name'] == 'Fire')
red = '--red' in sys.argv
phases = set()
bad = 0
for directory in (Path(a) for a in sys.argv[1:] if a != '--red'):
    log = (directory / 'smoke.txt').read_text()
    if not re.search(r'^END$', log, re.M):
        raise ValueError('Scene not completed: ' + str(directory))
    row = next(l for l in log.splitlines() if l.startswith('SCRSHOT name=loading '))
    state = dict(re.findall(r'(\w+)=(\S+)', row))
    time, progress = float(state['t']), int(state['prog'])
    phase = L.clock_index(time, fire['rate']) % len(fire['bitmaps'])
    phases.add(phase)
    reference = dict(PROGRESS=progress, T=time, LEVEL=int(state['level']), show={'ALWAYS'})
    actual = np.asarray(Image.open(directory / 'loading.png').convert('RGB'), float)
    swapped = dict(res, screens=dict(res['screens']))
    wrong_fire = dict(fire, bitmaps=list(reversed(fire['bitmaps'])))
    swapped['screens']['loading'] = [wrong_fire if t is fire else t for t in res['screens']['loading']]
    wanted = np.asarray(L.mock(res, 'loading', reference).convert('RGB'), float)
    other = np.asarray(L.mock(swapped, 'loading', reference).convert('RGB'), float)
    # Union of native flame alpha masks avoids counting unrelated UI/background.
    alpha = np.maximum(*(np.asarray(res['qbitmaps'][key])[..., 3] for key in fire['bitmaps'])) > 100
    x, y, w, h = fire['dst']; x += L.fuse_shift(fire, progress)
    roi = actual[y:y+h, x:x+w]
    want_roi, other_roi = wanted[y:y+h, x:x+w], other[y:y+h, x:x+w]
    # Shared glow pixels cannot identify an animation frame. Measure only pixels
    # where the two native frames differ substantially; never widen the tolerance.
    informative = alpha & (np.abs(want_roi - other_roi).max(axis=2) >= 20)
    if informative.sum() < 5:
        raise ValueError('Native frames have too few discriminating pixels')
    right = np.abs(roi - want_roi)[informative].mean()
    wrong = np.abs(roi - other_roi)[informative].mean()
    if red and phase == 1:
        right, wrong = wrong, right
    print(directory.name, 'clock', time, 'phase', phase, 'error', round(right, 3), 'other', round(wrong, 3))
    if right > 15 or wrong < right + 3:
        bad += 1
if phases != {0, 1}:
    raise ValueError('Both native fire phases must be captured')
print('failures', bad)
raise SystemExit(bool(bad))
