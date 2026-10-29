#!/usr/bin/env python3
"""Accept L3's real interior/talk/dialogue intro, not completion of its race.

--old-bot restores the driver's prior choice of travelling by car.
An executable compiled with MSN_INTERIOR_ALIAS_OLD=1 must also fail.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('campaign', ROOT / 'tools/bots/allrisk_missions.py')
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--binary', required=True, type=Path)
ap.add_argument('--data', required=True, type=Path)
ap.add_argument('--out', required=True, type=Path)
ap.add_argument('--old-bot', action='store_true')
ap.add_argument('--log', type=Path, help='inspect a retained run instead of replaying')
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
files = campaign.load_runner().level_files(a.data.resolve(), 3)
args = [str(files[k]) for k in ('level', 'player', 'roads', 'msn')]
missions, plans, errors, _ = campaign.catalog(a.binary.resolve(), args)
index = next(i for i, row in missions.items() if row['id'] == 'm1')
if a.log:
    text = a.log.read_text()
else:
    env = dict(os.environ, BW_LEVEL='3')
    if a.old_bot:
        env['ALLRISK_INTERIOR_OLD'] = '1'
    run = subprocess.run([str(a.binary.resolve()), *args, '--mode', 'mission',
                          '--mission', str(index), '--secs', '20', '--out', str(a.out)],
                         env=env, capture_output=True, text=True, timeout=120)
    text = run.stdout + run.stderr
    (a.out / 'runtime.tsv').write_text(text)
trace, result = campaign.parse_trace(text, index, plans)
intro = [t for t in trace if t['phase'] == 0]
ok = (not errors and result is not None and all(t['matches'] for t in trace)
      and [t['objective'] for t in intro] == ['interior', 'talkto', 'dialogue']
      and len(intro) == 3 and intro[1]['position'][1] < -10
      and any(t['phase'] == 1 and t['objective'] == 'race' for t in trace))
print(f'{"PASS" if ok else "FAIL"} intro={[t["objective"] for t in intro]} '
      f'main={any(t["phase"] == 1 for t in trace)} disc_errors={len(errors)}')
raise SystemExit(not ok)
