#!/usr/bin/env python3
"""Compare actual EBOOT screenshots from the unchanged base and a JSON size override.

--captures points to a directory with typo-gate-base/new/old, created by the
headless runtime. --old keeps the same changed-frame requirement and selects the
UI_TYPO_SIZE_OLD capture; this must fail. No geometry is simulated here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--captures', type=Path, required=True)
    p.add_argument('--old', action='store_true')
    a = p.parse_args()
    base = a.captures / 'typo-gate-base'
    candidate = a.captures / ('typo-gate-old' if a.old else 'typo-gate-new')
    for folder in (base, candidate):
        assert 'END' in (folder / 'smoke.txt').read_text().split(), 'runtime did not reach END'
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha(base / 'EBOOT.PBP') == sha(candidate / 'EBOOT.PBP'), 'different EBOOT: not a JSON-only comparison'
    before = np.asarray(Image.open(base / 'talk_a.png').convert('RGB'), np.int16)
    after = np.asarray(Image.open(candidate / 'talk_a.png').convert('RGB'), np.int16)
    # The notification is at the bottom; world/sky movement does not certify a changed font.
    delta = np.max(np.abs(before - after), axis=2)
    pixels = int((delta[205:270] > 12).sum())
    result = dict(old=a.old, eboot=sha(base / 'EBOOT.PBP'),
                  base_pack=sha(base / 'ui.shr'), candidate_pack=sha(candidate / 'ui.shr'), changed_text_pixels=pixels)
    print(json.dumps(result, indent=2))
    assert result['base_pack'] != result['candidate_pack'], 'JSON size did not change the loaded pack'
    assert pixels >= 100, 'JSON size did not change the actual notification frame'
    print('PASS: JSON size reaches the frame on the same EBOOT')


if __name__ == '__main__':
    main()
