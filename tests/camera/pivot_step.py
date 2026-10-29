#!/usr/bin/env python3
"""Check the production camera observer against independent frame motions.

The source helper is compiled, not reimplemented. Two mutations prove that
counting a pivot handoff or skipping its frame cannot pass this test.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import json
import subprocess
from pathlib import Path

from chase_motion import ROOT, function


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--control', choices=('old', 'blind'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    helper = function(read_main(ROOT / 'viewer/main.c'), 'camEyeStep')
    if args.control == 'old':
        helper = helper.replace('  float dp =', '  samePivot = 1;\n  float dp =', 1)
    if args.control == 'blind':
        helper = helper.replace('  float dp =', '  if (!samePivot) return -1.f;\n  float dp =', 1)
    source = '#include <math.h>\n#include <stdio.h>\n' + helper + r'''
int main(void) {
  float e[3], p[3], oldE[3], oldP[3]; int same;
  while (scanf("%f%f%f%f%f%f%f%f%f%f%f%f%d",
      e,e+1,e+2,p,p+1,p+2,oldE,oldE+1,oldE+2,oldP,oldP+1,oldP+2,&same)==13)
    printf("%.7f\n",camEyeStep(e,p,oldE,oldP,same));
}
'''
    (args.out / 'observer.c').write_text(source)
    subprocess.run(['cc', '-std=c11', '-O2', str(args.out / 'observer.c'),
                    '-lm', '-o', str(args.out / 'observer')], check=True)
    cases = []

    def case(label, eye, pivot, old_eye, old_pivot, same, expected):
        cases.append((label, [*eye, *pivot, *old_eye, *old_pivot, int(same)], expected))

    # Captured real car -> Homer handoff: rendered eye, look and FOV held.
    eye = [-162.963, 5.443, 243.472]
    car = [-164.071, .725 + 1.65 + .3, 235.273]
    homer = [-165.720, .824 + 1.5, 235.889]
    case('recorded exit holds eye', eye, homer, eye, car, False, 0)
    case('recorded entry holds eye', eye, car, eye, homer, False, 0)
    for hz in (30, 60, 120):
        for axis in range(3):
            old_eye, old_pivot = [10, 5, -20], [10, 1, -12]
            # Shared motion should be subtracted while following one subject.
            e, p = old_eye.copy(), old_pivot.copy()
            e[axis] += 40 / hz
            p[axis] += 40 / hz
            case('tracking translation', e, p, old_eye, old_pivot, True, 0)
            e[axis] += 2
            case('same-subject real jolt', e, p, old_eye, old_pivot, True, 2)
            # Handoffs must measure an actual eye displacement, even if the
            # subject moves by the exact same amount or far beyond 3 m.
            for delta in (.02, .6, 2, 10):
                for pivot_delta in (0, delta, -delta, 8):
                    e, p = old_eye.copy(), old_pivot.copy()
                    e[axis] += delta
                    p[axis] += pivot_delta
                    case('handoff retains real motion', e, p, old_eye, old_pivot, False, delta)
            p = old_pivot.copy()
            p[axis] += 4
            case('existing teleport filter', e, p, old_eye, old_pivot, True, -1)
    payload = '\n'.join(' '.join(map(str, row)) for _, row, _ in cases) + '\n'
    result = subprocess.run([str(args.out / 'observer')], input=payload,
                            text=True, capture_output=True, check=True)
    values = [float(v) for v in result.stdout.split()]
    assert len(values) == len(cases), 'missing observer results'
    failures = [{'case': name, 'actual': value, 'expected': expected}
                for (name, _, expected), value in zip(cases, values)
                if abs(value - expected) > .00002]
    report = dict(checks=len(cases), failures=failures, control=args.control)
    (args.out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"checks={len(cases)} failures={len(failures)} control={args.control}")
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
