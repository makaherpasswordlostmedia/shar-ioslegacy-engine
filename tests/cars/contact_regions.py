#!/usr/bin/env python3
"""Original snapshots must cover the contact's actual city resources.

--old-unguarded reproduces the former blind admission of any saved state.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins'))
import contact_slope as S


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-unguarded', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    hump = dict(port_start=[-150.447113, -4.22149372, -295.849701])
    right = dict(throw_cm=[-114, 8.9, -452])
    cases = [
        (hump, 'build/ps2ref/state_l1_incar.p2s', False, 'l1z6'),
        (hump, 'build/twins/o4/b2_loop/snap_12000.p2s', False, 'l1z6'),
        (hump, 'build/twins/o4/b2_loop/snap_21000.p2s', True, 'l1z6'),
        (right, 'build/twins/o4/b2_loop/snap_12000.p2s', False, 'l1r3'),
        (right, 'build/twins/o4/b2_loop/snap_15000.p2s', True, 'l1r3'),
    ]
    rows, failures = [], 0
    for spec, state, expected, region in cases:
        if args.old_unguarded:
            admitted, detail = True, {'required': []}
        else:
            try:
                detail = S.contact_regions(ROOT / state, spec)
                admitted = True
            except ValueError as e:
                detail, admitted = {'error': str(e)}, False
        ok = admitted == expected
        if admitted and expected and not args.old_unguarded:
            ok &= region in detail['required'] and region in detail['initial_safe']
        if not admitted:
            ok &= region in detail['error']
        failures += not ok
        rows.append(dict(state=state, expected=expected, admitted=admitted, ok=bool(ok), detail=detail))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + '\n')
    print(f"{'FAIL' if failures else 'PASS'} contact region cases={len(rows)} failures={failures}")
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
