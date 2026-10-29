#!/usr/bin/env python3
"""Finite host acceptance of authored tree/pole break families on all seven levels.

Uses the user's original P3D/ATC data, the exported PRP2/SPR1, and the real
Homer/game/prop modules. Does not start a bot, emulator or background service.
Pass --levels with a directory containing lN/level.shr; --l6 can use a separate
already accepted L6 export. Old game code and staged assets are negative controls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import prp2_export as P
from stateprop_dump import ART, atc_table

# Indices established from the original composites, not inferred from port output.
TREE_POLE = {14, 15, 20, 21, 22, 23, 25, 26, 27, 28, 29}


def inventory(level):
    atc = atc_table()
    families, clips, sources = {}, set(), {}
    files = P.level_files(ART, level)
    for file in files + [ART / f'l0{level}_fx.p3d']:
        if not file.exists():
            continue
        sources[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
        for ent in P.read(file).children:
            if ent.id == 0x3001000:
                clips.add(struct.unpack_from('<I', ent.data)[0])
            if ent.id != 0x3f00002:
                continue
            a = next((c for c in ent.children if c.id == 0x3000600), None)
            if not a:
                continue
            cls, phys = struct.unpack_from('<II', a.data)
            if cls == 2 or phys >= len(atc):
                continue
            idx = P.BREAK_BY_ATC.get(atc[phys]['breakable'])
            if idx in TREE_POLE:
                families.setdefault(idx, set()).add(P.N(ent))
    sources[str((ART / 'atc/atc.p3d').relative_to(ROOT))] = hashlib.sha256((ART / 'atc/atc.p3d').read_bytes()).hexdigest()
    return dict(required=sorted(set(families) & clips),
                unavailable={str(i): sorted(families[i]) for i in sorted(set(families) - clips)},
                families={str(i): sorted(n) for i, n in sorted(families.items())}, sources=sources)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--levels', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--l6', type=Path)
    ap.add_argument('--negative-levels', type=Path, required=True,
                    help='frozen older lN/level.shr inputs for all seven levels; never use refreshed output')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    old_game = args.out / 'old-game.c'
    old_game.write_bytes(subprocess.check_output(['git', 'show', 'c5df6e4:viewer/game.c'], cwd=ROOT))
    binaries = {}
    for label, game in [('green', ROOT / 'viewer/game.c'), ('old-hit', old_game)]:
        binary = args.out / label
        modules = ['homer', 'skin', 'props', 'stateprops', 'coins', 'car', 'col', 'collect']
        subprocess.run(['cc', '-std=c99', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'),
                        str(ROOT / 'tests/fx/tree_kicks.c'), str(game),
                        *[str(ROOT / f'viewer/{m}.c') for m in modules], '-lm', '-o', str(binary)], check=True)
        binaries[label] = binary.resolve()
    result, passed = {}, True
    for level in range(1, 8):
        inv = inventory(level)
        path = args.l6 if level == 6 and args.l6 else args.levels / f'l{level}/level.shr'
        path = path.resolve()
        if not path.is_file() or not inv['required']:
            raise RuntimeError(f'missing exported level/families: L{level} {path}')
        inv['export_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        runs = {}
        for label in ['green', 'old-hit', 'old-assets']:
            binary = binaries['green' if label == 'old-assets' else label]
            old_path = args.negative_levels / f'l{level}/level.shr'
            data = old_path if label == 'old-assets' else path
            log = args.out / f'l{level}-{label}.log'
            with log.open('w') as stream:
                run = subprocess.run([str(binary), str(data), str(ROOT / 'build/homer.shr'),
                                      *map(str, inv['required'])], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=60)
            lines = log.read_text().splitlines()
            if run.returncode not in (0, 1) or not lines:
                raise RuntimeError(f'{label} L{level}: no valid test result, rc={run.returncode} {data}')
            runs[label] = dict(rc=run.returncode, log=str(log), summary=lines[-1])
        passed &= runs['green']['rc'] == 0
        inv['runs'] = runs
        result[level] = inv
        print(f'L{level} families{inv["required"]}: ' + ', '.join(f'{k}={v["summary"]}' for k, v in runs.items()), flush=True)
    # The acceptance must actually reject both the former hit rule and missing assets.
    passed &= any(r['runs']['old-hit']['rc'] == 1 for r in result.values())
    passed &= any(r['runs']['old-assets']['rc'] == 1 for r in result.values())
    (args.out / 'report.json').write_text(json.dumps(dict(passed=passed, levels=result), indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
