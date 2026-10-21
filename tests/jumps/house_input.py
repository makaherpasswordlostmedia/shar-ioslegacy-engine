#!/usr/bin/env python3
"""Check the house coast input against the observer's saved pad recipe.

Reads existing local evidence only; never starts PCSX2. The old reference
with coast=99 must fail even when the gameplay gate accepts known differences.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--observer', type=Path, default=Path.home() / 'Downloads/shar-psp-ps2-w')
    p.add_argument('--ref', type=Path, default=ROOT / 'tests/jumps/house_ps2.tsv')
    p.add_argument('--trace', type=Path)
    a = p.parse_args()
    name = 'ps2_v103_house100_coast'
    recipe_path = a.observer / f'tools/twins/recipes/{name}_repeat.json'
    trace_path = a.observer / f'build/twins/o4/{name}/trace.tsv'
    recipe = json.loads(recipe_path.read_text())
    assert recipe['coast'] and not recipe['writes'], 'not an input-only coast recipe'
    cross = [v for v in recipe['pad'] if v[1] == 'cross']
    assert len(cross) == 2 and cross[0] == [0, 'cross', 1] and cross[1][2] == 0, 'not one permanent release'
    release = cross[1][0]
    with trace_path.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    row = next(r for r in rows if float(r['rel']) >= release)
    along = -float(row['mat[14]']) + recipe['lip'][2]
    refs = [l.split() for l in a.ref.read_text().splitlines() if l and not l.startswith('#')]
    assert sorted(r[0] for r in refs) == ['h100c', 'h80', 'h90'], 'missing or duplicate house references'
    ref = next(r for r in refs if r[0] == 'h100c')
    assert abs(float(ref[7]) - along) <= .0051, f'coast position: ref={ref[7]}, observer={along:.3f}'
    if a.trace:
        with a.trace.open() as f:
            port = list(csv.DictReader(f, delimiter='\t'))
        # Samples record position after the step but throttle before it. Exclude
        # the one sample crossing the release point, then require coast forever.
        start = next(i for i, r in enumerate(port) if float(r['along']) >= along)
        assert len(port) - start > 25, 'no post-release observation'
        assert all(float(r['throttle']) == 0 for r in port[start + 1:]), 'gas reapplied after coast release'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({'status': 'PASS', 'release_frame': release, 'release_along': along,
                      'recipe_sha256': digest(recipe_path), 'ps2_trace_sha256': digest(trace_path),
                      'ref_sha256': digest(a.ref)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
