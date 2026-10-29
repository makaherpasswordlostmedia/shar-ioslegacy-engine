#!/usr/bin/env python3
"""421 partial: hedge fence glances use the unchanged PS2 placement comparator.
Only recorded hedge003 A/B forward runs; capsules/head-on remain a separate gate.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/twins'))
import walls_family as W
flags = '-DCAR_WALL_FRICTION_OLD=1' if '--old' in sys.argv else ''
_, rows, _, _ = W.run_side(1, 'hedge_glance_old' if flags else 'hedge_glance', flags)
want = {'hedge003_Af', 'hedge003_Bf'}
probes = [r for r in rows if r['trial'] in want and r['test'] == 'разгон вперёд']
ok = len(probes) == len(want) and {r['trial'] for r in probes} == want
for r in probes:
    good = r['verdict'] == 'совпало'
    ok &= good
    print(f"{'PASS' if good else 'FAIL'} {r['trial']}: PS2 {r['v_o']:.2f}, port {r['v_p']:.2f} m/s; {r['verdict']}")
print(f"{'PASS' if ok else 'FAIL'} hedge glances {len(probes)}/{len(want)}")
raise SystemExit(0 if ok else 1)
