#!/usr/bin/env python3
"""Боты по маршрутам трамплинов (пункт 10): tools/cartest/routes_run.c на всех трамплинах build/sandbox/routes-l1.tsv в 6
процессах + два контроля из данных, сводка build/sandbox/routes-result.json. Без AI и сети.
  python3 tools/cartest/routes_bots.py
Контроли: «стена» — маршрут jumpzone18 со стартом на 25 м назад, через ступень, которую отверг подъезд (routes.py
остановил подъезд у неё), обязан «не доехать»; «хороший» — лестница пожарной машины у Kwik-E-Mart (jumpzone1, подъём
наклонного ящика) обязана хотя бы на одной скорости «доехать» (прыжок, посадка, едет дальше)."""
import collections, concurrent.futures, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
B = ROOT / 'build/routes_run'
subprocess.run(['cc', '-std=c11', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'), str(ROOT / 'tools/cartest/routes_run.c')] +
               [str(ROOT / 'viewer' / f) for f in ('car.c', 'col.c', 'props.c', 'stateprops.c', 'coins.c')] + ['-lm', '-o', str(B)], check=True)
routes = json.loads((ROOT / 'build/sandbox/routes-l1.json').read_text())
tsv = (ROOT / 'build/sandbox/routes-l1.tsv').read_text().splitlines()
j18 = next(r for r in routes['ramps'] if r['name'] == 'jumpzone18')
dx, dz = j18['direction']; lx, ly, lz = j18['lip']
ctl = ROOT / 'build/sandbox/routes-controls.tsv'
ctl.write_text('control_wall\t%.3f %.3f %.3f\t%.4f %.4f\t%.3f %.3f %.3f\t-1\n' % (lx - dx * 25, ly - 3.0, lz - dz * 25, dx, dz, lx, ly, lz))
jobs = [(str(ROOT / 'build/sandbox/routes-l1.tsv'), k, 6) for k in range(6)] + [(str(ctl), 0, 1)]
def run(j):
    return subprocess.run([str(B), str(ROOT / 'build/level.shr'), j[0], str(j[1]), str(j[2])], capture_output=True, text=True, check=True).stdout
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
    out = ''.join(ex.map(run, jobs))
rows = [l.split('\t') for l in out.splitlines() if l.strip()]
C = ('ramp', 'kmh', 'dh', 'dl', 'passed', 'vlip', 'landed', 'lx', 'ly', 'lz', 'surface', 'flight', 'moved', 'rec', 'flip', 'glass', 'ok')
rows = [dict(zip(C, r)) for r in rows]
res = {}
for r in rows:
    R = res.setdefault(r['ramp'], dict(bySpeed={}, surfaces=collections.Counter(), deadEnds=[]))
    S = R['bySpeed'].setdefault(r['kmh'], dict(runs=0, ok=0, glass=0, landed=0))
    S['runs'] += 1; S['ok'] += int(r['ok']); S['glass'] += int(r['glass'] == '1'); S['landed'] += int(r['landed'])
    R['surfaces'][r['surface']] += 1
    if r['landed'] == '1' and r['ok'] == '0' and float(r['moved']) < 15 and len(R['deadEnds']) < 5:
        R['deadEnds'].append(dict(kmh=int(r['kmh']), headingDeg=float(r['dh']), sideM=float(r['dl']), at=[float(r['lx']), float(r['ly']), float(r['lz'])],
                                  surface=r['surface'], moved10s=float(r['moved'])))
for name, R in res.items():
    R['surfaces'] = dict(R['surfaces'])
    R['band90'] = [int(k) for k, S in sorted(R['bySpeed'].items(), key=lambda kv: int(kv[0])) if S['runs'] and S['ok'] / S['runs'] >= 0.9]
    R['best'] = max(((int(k), S['ok'] / S['runs']) for k, S in R['bySpeed'].items() if S['runs']), key=lambda t: t[1], default=(0, 0))
wall, good = res.get('control_wall', {}), res.get('jumpzone1', {})
wall_ok = wall and sum(S['ok'] for S in wall['bySpeed'].values()) == 0 and wall['surfaces'].get('blocked', 0) > 0
good_ok = good and sum(S['ok'] for S in good['bySpeed'].values()) > 0
out = dict(kind='routes-result-v1', runs=len(rows), perRamp=res, controls=dict(wallBlocked=bool(wall_ok), ladderReached=bool(good_ok)),
           rule='успех: кромка пройдена, посадка на колёса, за 10 с после посадки 15 м и дальше, без возврата; 135 заездов на трамплин: '
                '40–120 км/ч × подход к кромке под углом ±5° × промах ±1 м', note='наблюдения ботов на Mac; «весело ли» решает Роб на PSP')
RR = ROOT / 'build/sandbox/routes-result.json'   # чужие разделы (roofs из tools/bots/roofs.py) сохраняются
old = json.loads(RR.read_text()) if RR.exists() else {}
out = {**{k: v for k, v in old.items() if k not in out}, **out}
RR.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print('заездов %d; контроль «стена» не доехал: %s; лестница доехала: %s' % (len(rows), wall_ok, good_ok))
for name in [r.split('\t')[0] for r in tsv]:
    R = res.get(name)
    if not R: continue
    tot = sum(S['ok'] for S in R['bySpeed'].values()); runs = sum(S['runs'] for S in R['bySpeed'].values())
    gl = sum(S['glass'] for S in R['bySpeed'].values())
    print('%-11s удачно %3d/%3d  лучшая %3d км/ч %3.0f%%  полоса ≥90%%: %-18s стекло %3d  %s' % (name, tot, runs, R['best'][0], R['best'][1] * 100,
          ','.join(map(str, R['band90'])) or '—', gl, R['surfaces']))
print('routes_bots: ' + ('PASS' if wall_ok and good_ok else 'FAIL') + ' (контроли)')
sys.exit(0 if wall_ok and good_ok else 1)
