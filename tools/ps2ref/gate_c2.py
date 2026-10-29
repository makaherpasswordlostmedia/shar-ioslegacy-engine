#!/usr/bin/env python3
"""Offline validation is not a new emulator replay.
--self-test: adversarial gate tests (no PCSX2)
--check A.tsv B.tsv --frames N: validate archived traces in a fresh result directory
Live capture requires the isolated profile and unattended input gates first.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from trace import same

ROOT = Path(__file__).resolve().parents[2]


def self_test(d):
    a, b = d / 'a.tsv', d / 'b.tsv'
    good = 'frame\tmat0\n0\t1\n2\t2\n4\t3\n'
    cases = {
        'empty': ('frame\tmat0\n', 'frame\tmat0\n'),
        'schema': (good, good.replace('mat0', 'other')),
        'truncated': (good.rsplit('4\t3', 1)[0], good.rsplit('4\t3', 1)[0]),
        'gap': (good.replace('2\t2\n', ''), good.replace('2\t2\n', '')),
        'duplicate': (good + '4\t3\n', good + '4\t3\n'),
        'nonfinite': (good.replace('4\t3', '4\tnan'), good.replace('4\t3', '4\tnan')),
        'different': (good, good.replace('4\t3', '4\t4')),
        'missing': (good, None),
    }
    results = {}
    for name, (x, y) in cases.items():
        a.write_text(x)
        target = d / 'missing.tsv' if y is None else b
        if y is not None: b.write_text(y)
        results[name] = not same(a, target, expected_frames=6)
        print('RED input rejected:', name, results[name])
    a.write_text(good); b.write_text(good)
    results['valid'] = same(a, b, expected_frames=6)
    return all(results.values()), results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-test', action='store_true')
    mode.add_argument('--check', nargs=2, type=Path)
    p.add_argument('--frames', type=int)
    a = p.parse_args()
    root = ROOT / 'build/ps2ref/gates'; root.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'), dir=root))
    result = {'mode': 'offline-self-test' if a.self_test else 'archived-traces', 'fresh_live_capture': False, 'ok': False}
    try:
        if a.self_test:
            result['ok'], result['checks'] = self_test(d)
        else:
            if a.frames is None: raise ValueError('--frames from the recording is required')
            result['sources'] = []
            for i, src in enumerate(a.check):
                dest = d / f'run{i}.tsv'
                shutil.copyfile(src, dest)
                result['sources'].append({'path': str(src.resolve()), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
            result['ok'] = same(d / 'run0.tsv', d / 'run1.tsv', expected_frames=a.frames)
    except (OSError, ValueError) as e:
        result['error'] = str(e)
    (d / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('RESULT:', 'OK' if result['ok'] else 'FAIL', d)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
