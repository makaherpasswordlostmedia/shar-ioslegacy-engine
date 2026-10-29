#!/usr/bin/env python3
"""Real traffic profiles, bounded source selector and shared positional DSP.

Rebuilds only tiny resident-bank fixtures, preserves the existing resource IDs,
compares the default exporter byte-for-byte and rejects a 2D spatial mutation.
No emulator, background worker, sound output or deployment.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import audio_export as AE
from traffic_export import level_script


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='build/traffic-engines')
    ap.add_argument('--stage', default='build/ship_stage')
    a = ap.parse_args()
    out = ROOT/a.out
    out.mkdir(parents=True, exist_ok=True)
    baseline = types.ModuleType('baseline_export')
    baseline.__file__ = str(ROOT/'tools/audio_export.py')
    exec(subprocess.check_output(['git', 'show', 'a100722:tools/audio_export.py'], cwd=ROOT, text=True), baseline.__dict__)
    summary = []
    for lv in range(1, 8):
        stage = ROOT/a.stage/('' if lv == 1 else f'l{lv}')/'audio'
        bank = (stage/'sfx.sab').read_bytes()
        nres, = struct.unpack_from('<I', bank, 8)
        roff, = struct.unpack_from('<I', bank, 20)
        coff, = struct.unpack_from('<I', bank, 32)
        names = [bank[roff+i*48:roff+i*48+24].split(b'\0')[0].decode() for i in range(nres)]
        hero = bank[coff:coff+16].split(b'\0')[0].decode()
        eo, es = struct.unpack_from('<II', bank, 80)
        cars = [v[0] for v in level_script(lv)[0]]
        kw = dict(car_name=hero, sfx_names=names, music_sel=[], ext=bank[eo:eo+es], quiet=True)
        path = out/f'l{lv}'
        baseline.build_pack(str(path/'baseline'), **kw)
        AE.build_pack(str(path/'same'), **kw)
        assert (path/'baseline/sfx.sab').read_bytes() == (path/'same/sfx.sab').read_bytes(), 'default export changed'
        rep = AE.build_pack(str(path/'audio'), **kw, extra_cars=cars)
        new = (path/'audio/sfx.sab').read_bytes()
        nr, = struct.unpack_from('<I', new, 20)
        nc, = struct.unpack_from('<I', new, 32)
        assert new[nr:nr+nres*48] == bank[roff:roff+nres*48], 'existing resource IDs changed'
        assert new[nc:nc+152] == bank[coff:coff+152], 'hero profile changed'
        nf, = struct.unpack_from('<I', bank, 12)
        fo, = struct.unpack_from('<I', bank, 28)
        nfo, = struct.unpack_from('<I', new, 28)
        do, ds = struct.unpack_from('<II', bank, 36)
        ndo, = struct.unpack_from('<I', new, 36)
        assert new[nfo:nfo+nf*32] == bank[fo:fo+nf*32], 'existing file/loop metadata changed'
        assert new[ndo:ndo+ds] == bank[do:do+ds], 'existing VAG payload changed'
        summary.append(dict(level=lv, profiles=rep['cars'], added_bytes=len(new)-len(bank),
                            sha256=hashlib.sha256(new).hexdigest(), default_identical=True))

    main_source = read_main(ROOT/'viewer/main.c')
    start = main_source.index('static void trafficMotorFrame(')
    end = main_source.index('static float cardHudT,', start)
    selector = main_source[start:end]
    template = (ROOT/'tests/sound/traffic_engines.c.in').read_text().replace('SELECTOR', selector)
    mutant = out/'audio_2d.c'
    audio = (ROOT/'viewer/audio.c').read_text()
    needle = 'enginePosition(e,spatialPoint(x,y,z,4.f,60.f));'
    assert audio.count(needle) == 1
    mutant.write_text(audio.replace(needle, 'MixPoint old={0};enginePosition(e,old);'))
    hashes = {}
    for name, source, expected in [('green', ROOT/'viewer/audio.c', 0), ('red-2d', mutant, 1), ('copy', ROOT/'viewer/audio.c', 0), ('stale', ROOT/'viewer/audio.c', None)]:
        code = out/(name+'.c')
        code.write_text(template.replace('AUDIO_SOURCE', str(source)))
        exe = out/name
        flags = ['-DMIX_JOB_COPY=1'] if name in ('copy', 'stale') else []
        if name == 'stale': flags += ['-DMIX_JOB_RED=1']
        subprocess.run(['cc', '-std=c11', '-O2', '-DAUDIO_HOST', '-DSKIN_HOST', '-DSKID_HOST', *flags, '-I', str(ROOT/'viewer'),
                        str(code), str(ROOT/'viewer/skid.c'), str(ROOT/'viewer/car.c'), str(ROOT/'viewer/col.c'), '-lm', '-o', str(exe)], check=True)
        for lv in range(1, 8):
            r = subprocess.run([str(exe), str(out/f'l{lv}/audio')+'/'], text=True, capture_output=True)
            (out/f'{name}-l{lv}.log').write_text(r.stdout+r.stderr)
            print(lv, r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr)
            if expected is not None and r.returncode != expected:
                raise SystemExit('Unexpected traffic engine gate result')
            if 'pcm=' not in r.stdout:
                raise SystemExit('Incomplete traffic PCM test')
            hashes[name, lv] = r.stdout.strip().split('pcm=')[-1]
            if name == 'copy' and hashes[name, lv] != hashes['green', lv]:
                raise SystemExit('Shared DSP job copy changed PCM')
            if name == 'stale' and hashes[name, lv] == hashes['green', lv]:
                raise SystemExit('Stale-job negative did not change PCM')
            if name == 'red-2d' and 'FAIL right-hand engine pans right' not in r.stdout:
                raise SystemExit('Spatial mutation did not reach the actual mixer checks')
    (out/'banks.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('PASS L1-L7 authored traffic engines, existing bank IDs and bounded spatial mixer; 2D negative rejected')


if __name__ == '__main__':
    main()
