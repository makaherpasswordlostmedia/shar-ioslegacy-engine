#!/usr/bin/env python3
"""L1-L7 costume catalogue/packages and actual wardrobe input state machine.

--export builds only wardrobe data by real ship rules. --gate checks OLD catalogue
filenames on every L2-L7, plus absent package, mismatched price and missing costume.
Expected names/prices/models come directly from rewards.mfk, not skins_export.
No emulation/rendering or physical PSP acceptance is claimed by this host gate.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'hit-and-run-web/source/game'
PY = ROOT / '.venv/bin/python'

def contract(level):
    text = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text())
    rows = []
    for args in re.findall(r'BindReward\s*\(([^)]+)\)', text):
        a = [v.strip().strip('"') for v in args.split(',')]
        if len(a) >= 5 and a[2] == 'skin' and int(a[4]) == level:
            rows.append((a[0], a[1].replace('\\', '/').split('/')[-1][:-4], int(a[5]) if len(a) > 5 else 0))
    assert len(rows) == 4, (level, rows)
    return rows

def filenames(level, rows):
    if level > 1:
        return ['player.shr', 'skin1.shr', 'skin2.shr', 'skin3.shr']
    return ['homer.shr'] + [f'homer-{r[1]}.shr' for r in rows[1:]]

def execute(cmd, log, env=None):
    with log.open('w') as out:
        return subprocess.run(cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT).returncode

def ui_check(path, prices, names):
    data = path.read_bytes()
    h = struct.unpack_from('<32I', data)
    assert data[:4] == b'UIP1' and h[1] == 1 and h[24] == len(data), 'UIP1 header'
    nstr, off = h[10:12]
    strings = [data[p:data.index(b'\0', p)].decode('latin1') for p in struct.unpack_from(f'<{nstr}I', data, off)]
    sys.path.insert(0, str(ROOT / 'tools'))
    import ui_export as ui
    bible = ui.load_bible(ui.LANG)
    expected_names = [bible(name.upper()) or name for name in names]
    expected_prices = ['' if p == 0 else f'{p} {bible("COINS") or "coins"}'.upper() for p in prices]
    selectors = []
    for i in range(h[4]):
        item = data[h[5] + i * 64:h[5] + (i + 1) * 64]
        first, count = struct.unpack_from('<HH', item, 28)
        if item[4] == 5 and count == 4: selectors.append(strings[first:first + count])
    assert expected_names in selectors, ('UI costume names', expected_names, selectors)
    assert expected_prices in selectors, ('UI prices', expected_prices, selectors)

def inspect_level(base, level):
    folder = base if level == 1 else base / f'l{level}'
    rows = contract(level); expected_files = filenames(level, rows)
    lines = [line.split() for line in (folder / 'skins.txt').read_text().splitlines()]
    skins = [line[1:] for line in lines if line[0] == 'skin']
    assert skins == [[r[0], file, str(r[2])] for r, file in zip(rows, expected_files)], ('catalogue', skins)
    # Independent P3D locator traversal: source PurchaseSkin position, including child matrix.
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from p3d import read, walk, string
    expected_spots = []
    for f in sorted((GAME / 'art').glob(f'l{level}i*.p3d')):
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            name, pos = string(c.data)
            kind, count = struct.unpack_from('<II', c.data, pos)
            values = c.data[pos + 8:pos + 8 + 4 * count].split(b'\0')
            if b'PurchaseSkin' not in values: continue
            xyz = struct.unpack_from('<3f', c.data, pos + 8 + 4 * count)
            for child in c.children:
                if child.id == 0x3000006:
                    _, p = string(child.data); xyz = struct.unpack_from('<16f', child.data, p + 16)[12:15]; break
            expected_spots.append([xyz[0], xyz[1], -xyz[2]])
    spots = [[float(v) for v in line[1:4]] for line in lines if line[0] == 'spot']
    assert len(spots) == len(expected_spots) and spots, ('spots', spots, expected_spots)
    assert all(abs(a - b) <= .006 for p, q in zip(spots, expected_spots) for a, b in zip(p, q)), 'locator coordinates'
    ui_check(folder / 'wardrobe.shr', [r[2] for r in rows], [r[0] for r in rows])
    prefix = dict(homer='hom', bart='brt', lisa='lsa', marge='mrg', apu='apu')[rows[0][0]]
    fingerprints = []
    for file in expected_files:
        data = (folder / file).read_bytes(); h = struct.unpack_from('<13I', data, 4)
        assert data[:4] == b'CHR1' and h[0] in (1, 2) and h[1] == len(data), file
        nclips, offset = h[5], h[10]
        clips = [data[offset + i * 80:offset + i * 80 + 48].split(b'\0')[0].decode() for i in range(nclips)]
        assert f'{prefix}_loco_idle_rest' in clips and 'ndr_in_car_idle' in clips, (file, clips)
        fingerprints.append(hashlib.sha256(data).hexdigest())
    assert len(set(fingerprints)) == 4, 'costume models must differ'
    return folder, rows, expected_files, spots

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', default='build/wardrobe-levels/data')
    ap.add_argument('--export', action='store_true'); ap.add_argument('--gate', action='store_true')
    ap.add_argument('--levels', nargs='+', type=int, default=list(range(1, 8)))
    args = ap.parse_args(); base = (ROOT / args.data).resolve(); base.mkdir(parents=True, exist_ok=True)
    out = base.parent / 'logs'; out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=str(ROOT / '.venv/bin') + os.pathsep + os.environ['PATH'], SHR_TMP=str(base.parent / 'tmp'), SHIP_LEVELS='2 3 4 5 6 7')
    rules = subprocess.check_output(['bash', 'tools/ship_files.sh', '--rules'], cwd=ROOT, env=env, text=True).splitlines()
    rules = [line.split('|') for line in rules]
    for level in args.levels:
        folder = base if level == 1 else base / f'l{level}'; folder.mkdir(parents=True, exist_ok=True)
        rows = contract(level); files = filenames(level, rows)
        cf = out / f'l{level}-contract.txt'; cf.write_text(''.join(f'{r[0]} {f} {r[2]}\n' for r, f in zip(rows, files)))
        if args.export:
            for f in files + ['wardrobe.shr', 'skins.txt']:
                name = f if level == 1 else f'l{level}/{f}'
                matches = [r for r in rules if r[0].strip() == name]
                if len(matches) != 1: raise SystemExit(f'missing/duplicate shipping rule: {name}')
                cmd = matches[0][3].strip().replace('{out}', str(folder / f))
                rc = execute(['bash', '-c', cmd], out / f'l{level}-export-{f}.txt', env)
                if rc: raise SystemExit(f'export FAIL L{level} {f}: {out}')
        try:
            _, _, _, spots = inspect_level(base, level)
        except (AssertionError, FileNotFoundError, ValueError) as e:
            print(f'CHECK L{level} packages FAIL {e}'); return 1
        mission = ROOT / 'build/ship_stage' / ('' if level == 1 else f'l{level}') / f'level{level:02d}.msn'
        cmd = [str(ROOT / 'build/wardrobe_levels_host'), str(folder), str(level), str(mission), str(cf)]
        green_log = out / f'l{level}-green.txt'; rc = execute(cmd, green_log)
        print(f'CHECK L{level} packages OK skins=4 spots={len(spots)} prices={[r[2] for r in rows]}')
        print(f'CHECK L{level} runtime {"FAIL" if rc else "OK"} log={green_log}')
        if rc: return 1
        if args.gate and level > 1:
            red = base.parent / 'red' / f'l{level}'; red.mkdir(parents=True, exist_ok=True)
            for f in files + ['wardrobe.shr']: shutil.copyfile(folder / f, red / f)
            red_env = dict(env, SKIN_CATALOG_OLD='1')
            if execute([str(PY), 'tools/skins_export.py', '--level', str(level), '--list', str(red / 'skins.txt')], out / f'l{level}-old-export.txt', red_env): return 1
            red_cmd = [cmd[0], str(red), *cmd[2:]]
            old_log = out / f'l{level}-old.txt'; old_rc = execute(red_cmd, old_log)
            if not old_rc or 'CHECK preview-loaded-distinct FAIL' not in old_log.read_text():
                print(f'CHECK L{level} OLD NOT CAUGHT'); return 1
            print(f'CHECK L{level} OLD caught missing preview/wear')
            # Corrupt price; a green gate must reject it independently of model loading.
            text = (folder / 'skins.txt').read_text()
            line = f'skin {rows[1][0]} {files[1]} {rows[1][2]}'
            (red / 'skins.txt').write_text(text.replace(line, line.rsplit(' ', 1)[0] + ' 1'))
            bad_log = out / f'l{level}-badprice.txt'
            if not execute(red_cmd, bad_log) or 'CHECK catalog-file-name-price FAIL' not in bad_log.read_text(): return 1
            # Missing costume differs from catalogue-path OLD; actual load must fail.
            (red / 'skins.txt').write_text(text); (red / files[3]).rename(red / (files[3] + '.absent'))
            if not execute(red_cmd, out / f'l{level}-missing-model.txt'): return 1
            # Absent wardrobe UI must never produce a green purchasing run.
            (red / 'wardrobe.shr').rename(red / 'wardrobe.shr.absent')
            if not execute(red_cmd, out / f'l{level}-missing-ui.txt'): return 1
    print('wardrobe levels gate: PASS'); return 0

if __name__ == '__main__': raise SystemExit(main())
