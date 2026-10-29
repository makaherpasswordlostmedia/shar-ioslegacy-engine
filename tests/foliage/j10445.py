#!/usr/bin/env python3
"""J10-8 on real COL/PRP/SPR data; retain #421 and compare wheel-rest OLD.

Usage: python3 tests/foliage/j10445.py OLD_L7 NEW_L7 CAR435_C OUT
CAR435_C is the accepted #435 snapshot; its hash is recorded in the proof.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

old, new, car, out = map(Path, sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
runs = []
for rest in (1, 0):
    exe = out / f'drive-restold{rest}'
    subprocess.run(['cc', '-std=c11', '-O2', '-DSKIN_HOST',
                    f'-DCAR_REST_TYRE_OLD={rest}', '-I', 'viewer',
                    'tests/foliage/drive445.c', str(car), 'viewer/col.c',
                    'viewer/props.c', 'viewer/coins.c', '-lm', '-o', str(exe)], check=True)
    for tag, level in (('old', old), ('new', new)):
        for speed in (20, 40, 60):
            p = subprocess.run([str(exe.resolve()), str(level), '155', '286',
                                '1.5707963', str(speed), '5'],
                               capture_output=True, text=True, check=True)
            name = f'restold{rest}-{tag}-{speed}'
            (out / f'{name}.txt').write_text(p.stdout)
            line = next(s for s in p.stdout.splitlines() if s.startswith('SUMMARY'))
            along = float(line.split('along ')[1].split()[0])
            runs.append(dict(case=name, along=along, summary=line))
            print(name, line, flush=True)
            if tag == 'new':
                assert along > 10, (name, line)
            if tag == 'old' and rest == 0 and speed == 20:
                assert along < 5, ('negative control did not reproduce', name, line)
proof = dict(status='PASS', runs=runs,
             inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (old, new, car, Path('viewer/col.c'))})
(out / 'result.json').write_text(json.dumps(proof, indent=2) + '\n')
print('PASS J10-8, 20/40/60, CAR_REST_TYRE_OLD=1/0; original-data negative reproduced')
