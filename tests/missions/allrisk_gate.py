#!/usr/bin/env python3
"""Real CPU world, disc-derived stage plan; old mission dispatch must fail this gate.
This accepts the bot tool, not completion of all gameplay missions.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('campaign', ROOT / 'tools/bots/allrisk_missions.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ap = argparse.ArgumentParser()
ap.add_argument('--binary', required=True, type=Path)
ap.add_argument('--data', type=Path)
ap.add_argument('--out', required=True, type=Path)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
runner = m.load_runner()
data = runner.data_root(a.data)
failed = 0
for level in range(2, 8):
    try:
        files = runner.level_files(data, level)
        args = [str(files[k]) for k in ('level', 'player', 'roads', 'msn')]
        missions, plans, errors, _ = m.catalog(a.binary.resolve(), args)
        assert not errors, f'disc/packet disagreement: {errors}'
        index = next(i for i, row in missions.items() if not row['flags'] & 15)
        dest = a.out / f'L{level}'
        dest.mkdir(exist_ok=True)
        run = subprocess.run([str(a.binary.resolve()), *args, '--mode', 'mission',
                              '--mission', str(index), '--secs', '3', '--out', str(dest)],
                             capture_output=True, text=True, timeout=120)
        (dest / 'runtime.tsv').write_text(run.stdout + run.stderr)
        trace, result = m.parse_trace(run.stdout, index, plans)
        assert run.returncode == 0 and trace and result is not None, 'missing real stage/outcome'
        assert all(t['matches'] for t in trace), 'runtime objective differs from disc plan'
        assert (dest / f'm{index}.in').exists(), 'input replay not retained'
        print(f'L{level} PASS disc_stages={sum(map(len, plans.values()))} visited={len(trace)}')
    except (AssertionError, subprocess.SubprocessError, OSError, ValueError) as error:
        failed += 1
        print(f'L{level} FAIL {error}')
print(f'RESULT {"FAIL" if failed else "PASS"} failures={failed}')
raise SystemExit(bool(failed))
