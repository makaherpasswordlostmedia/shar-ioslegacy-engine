#!/usr/bin/env python3
"""Check submitted frames after real DEV restart; actual load/IO faults are red."""
import argparse, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def native(run, level):
    text = (run / 'smoke.txt').read_text()
    failures = []
    if 'END' not in text.splitlines(): failures.append('missing END')
    if not re.search(rf'^SVDEV load slot=3 level={level}$', text, re.M): failures.append('wrong DEV level')
    if not re.search(rf'^LEVEL ev=load n={level} loaded={level} ', text, re.M): failures.append('missing actual level load')
    frames = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in text.splitlines() if l.startswith('FIRSTFRAME ')]
    seconds = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in text.splitlines() if l.startswith('FIRSTSEC ')]
    if not frames or not seconds: failures.append('missing submitted-frame counters')
    if any(int(x['level']) != level or int(x['missvis']) != 0 for x in frames): failures.append('visible cells missing in first frame')
    if any(int(x['level']) != level or int(x['frames']) < 2 or int(x['miss_frames']) != 0 or int(x['max']) != 0 for x in seconds): failures.append('visible cells missing in first second')
    one = re.search(rf'^LOADONE level={level} .+$', text, re.M)
    if not one: failures.append('place was not prepared under loading screen')
    elif not frames or text.index(one[0]) > text.index('FIRSTFRAME '): failures.append('place loaded after first frame')
    stats = [dict(re.findall(r'(\w+) ([^ ]+)', l)) for l in text.splitlines() if l.startswith('STAT ')]
    for row in stats:
        for k in ('readerr', 'allocfail', 'memfail', 'gebad', 'geskip'):
            if k not in row or float(row[k]) != 0: failures.append('bad/missing '+k)
    return failures, frames, seconds

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', type=Path); a = ap.parse_args()
    rows = []
    for level in range(1, 8):
        run = a.runs / f'green-l{level}'; bad, frames, seconds = native(run, level)
        assert not bad, (level, bad)
        rows.append(dict(level=level, frames=frames, seconds=seconds, eboot_sha256=hashlib.sha256((run/'EBOOT.PBP').read_bytes()).hexdigest()))
    old, oldfr, oldsec = native(a.runs/'old-l6', 6)
    assert 'visible cells missing in first frame' in old and any(int(r['missvis']) > 0 for r in oldfr), old
    fault, faultfr, faultsec = native(a.runs/'cell-fault', 1)
    assert 'visible cells missing in first frame' in fault and any(int(r['missvis']) > 0 for r in faultfr), fault
    assert len({r['eboot_sha256'] for r in rows}) == 1, 'green binary changed'
    report = dict(green=rows, old356=dict(failures=old, frames=oldfr, seconds=oldsec), actual_io_fault=dict(failures=fault, frames=faultfr, seconds=faultsec))
    (a.runs/'gate.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS seven real DEV restarts: first frame/second0; actual OLD356 and IO fault caught')

if __name__ == '__main__': main()
