#!/usr/bin/env python3
"""Repeat FE contract acceptance on saved native pairs; never launch/delete a run.

The three native pairs must be produced by clock404_scenario,
load404_scenario and cold405_long_scenario using the documented NEW/OLD SDKs.
Audio export/backend/decode acceptance is separate: tests/fe_audio/gate.sh.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/fe-ps2/acceptance'
RUNS = ROOT / 'build/twins/scen/full'
OUT.mkdir(parents=True, exist_ok=True)
results = []

def run(name, script, args=(), expected=0):
    command = [sys.executable, str(ROOT / script), *map(str, args)]
    p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (OUT / (name + '.log')).write_text(p.stdout + p.stderr)
    ok = p.returncode == expected and ('PASS' if expected == 0 else 'FAIL') in p.stdout
    results.append(dict(name=name, command=command, rc=p.returncode, expected=expected, ok=ok))
    print(name, 'PASS' if ok else 'FAIL', 'rc', p.returncode)

clock = RUNS / 'c3fe-clock-a2-new/smoke.txt'
load = RUNS / 'c3fe-load-a3-new/smoke.txt'
cold = RUNS / 'c3fe-cold-a3-new'
run('clock-header', 'tests/menu/clock404_host.py')
run('clock-native', 'tests/menu/clock404_native.py', [clock])
run('clock-old', 'tests/menu/clock404_native.py', [RUNS / 'c3fe-clock-a2-old/smoke.txt'], 1)
run('load-native', 'tests/menu/clock404_native.py', ['--load', load])
run('load-old', 'tests/menu/clock404_native.py', ['--load', RUNS / 'c3fe-load-a3-old/smoke.txt'], 1)
run('audio-integrated', 'tests/fe_audio/integrated.py', [clock, '--out', OUT / 'audio-integrated.json'])
run('audio-integrated-old', 'tests/fe_audio/integrated.py', [RUNS / 'c3fe-clock-a2-old/smoke.txt'], 1)
text = clock.read_text()
audio_plants = {'not-ready': text.replace('ready_before=1', 'ready_before=0'),
                'changed-request': text.replace('req=1 ready_before=1', 'req=777 ready_before=1'),
                'forced-as-natural': text.replace('forced=1', 'forced=0')}
for name, data in audio_plants.items():
    planted = OUT / ('audio-plant-' + name + '.txt')
    planted.write_text(data)
    run('audio-plant-' + name, 'tests/fe_audio/integrated.py', [planted, '--asset', ROOT / 'build/fe_audio.sap'], 1)
for plant in ('options-tick', 'title-jump', 'prep-late'):
    run('clock-plant-' + plant, 'tests/menu/clock404_native.py', [clock, '--plant', plant], 1)
for plant in ('pending-lost', 'audio-changed'):
    run('load-plant-' + plant, 'tests/menu/clock404_native.py', ['--load', load, '--plant', plant], 1)
run('cold-native-plants', 'tests/title/cold_integration_check.py', [cold, '--plants'])
run('cold-old', 'tests/title/cold_integration_check.py', [RUNS / 'c3fe-cold-a3-old'], 1)
run('pulse-source', 'tests/title/start_phase_check.py', ['--source'])
run('pulse-source-old', 'tests/title/start_phase_check.py', ['--source', '--old'], 1)
run('pulse-native', 'tests/title/start_phase_check.py', [cold])
run('pulse-native-old', 'tests/title/start_phase_check.py', [RUNS / 'c3fe-cold-a3-old'], 1)
paths = list(ROOT.glob('viewer/*.c')) + list(ROOT.glob('viewer/*.h'))
paths += [ROOT / 'viewer/CMakeLists.txt', ROOT / 'tools/ship_rules.txt', ROOT / 'tools/fe_audio_export.py', ROOT / 'build/fe_audio.sap']
paths += list(ROOT.glob('build/fe-ps2/psp-*/CMakeCache.txt'))
paths += [ROOT / 'build/fe-ps2/audio-route-root/source.json', ROOT / 'build/fe-ps2/stage-inputs.json']
paths += list(ROOT.glob('tests/menu/*404*')) + list(ROOT.glob('tests/menu/*405*'))
paths += list(ROOT.glob('tests/title/*.py')) + list(ROOT.glob('tests/fe_audio/*'))
paths += list(ROOT.glob('build/fe-ps2/psp-*/EBOOT.PBP'))
paths += [ROOT / 'build/EBOOT.PBP', ROOT / 'build/ship_stage/EBOOT.PBP', ROOT / 'build/ship_stage/fe_audio.sap']
for name in ('c3fe-clock-a2-new', 'c3fe-clock-a2-old', 'c3fe-load-a3-new',
             'c3fe-load-a3-old', 'c3fe-cold-a3-new', 'c3fe-cold-a3-old'):
    paths += [p for p in (RUNS / name).iterdir() if p.name in ('smoke.txt', 'scenario.txt', 'EBOOT.PBP', 'intro.txt') or p.suffix == '.png']
artifacts = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(set(paths)) if p.is_file()}
manifest = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                results=results, artifacts=artifacts,
                limits=['Saved native runs, no PSP hardware acceptance',
                        'Native menu-only STAT has zero game frames; no FPS claim',
                        'Pulse midpoint and disabled demo are documented port rules',
                        'FE PCM decoding/backend proof does not establish full PS2 mix identity'])
facts = ROOT.parent / 'shar-psp-ps2-w/knowledge/facts'
manifest['observer_facts'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (facts / 'ps2-main-menu-runtime.yaml', facts / 'ps2-title-first-frame.yaml')}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
bad = sum(not r['ok'] for r in results)
print('RESULT', 'FAIL' if bad else 'PASS', 'runs', len(results), 'failures', bad, 'SHA artifacts', len(artifacts))
raise SystemExit(bool(bad))
