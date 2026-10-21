#!/usr/bin/env python3
"""Правки Роба 180/184: голоса улицы. Оригинал (близнец Б2, build/twins/b2/*/missing.tsv): за рулём читает реплики прохожих
generic_*/p_nhitbyc_* (чуть не сбит), p_hitbyc_* (сбит) и водителей трафика traffic1/d_carway_vm1_*; у порта их не было.
Порт: EBOOT в своём PPSSPPHeadless без окна, сценарий tests/traffic/streetvoice_scenario.txt — машина игрока проходит в 1,6 м
от прохожего на скорости (near), таранит стоящую машину трафика (carhit), сбивает прохожего на пути (pedhit). По строкам
STREETV smoke.txt: в каждой сцене своё событие и реплика пошла (said=1); у сбитого — без «чуть не» перед ударом.
Какой прохожий каким голосом и пороги «чуть не» — правило порта (на диске связи нет).

  python3 tests/traffic/streetvoice_twins.py [--eboot viewer/build/EBOOT.PBP]   зелёный
  python3 tests/traffic/streetvoice_twins.py --negative [--eboot ...]          красный: «flag streetvoff» — голоса молчат"""
import argparse, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins'))
WANT = {'near': 'near', 'carhit': 'car', 'pedhit': 'hit'}


def check(smoke, red=False):
    scene, got = None, {}
    for l in Path(smoke).read_text(errors='replace').splitlines():
        m = re.match(r'SCENE (\S+)', l)
        if m: scene = m.group(1); got[scene] = []; continue
        m = re.match(r'STREETV ev=(\S+) .*said=(\d)', l)
        if m and scene: got[scene].append((m.group(1), int(m.group(2))))
    bad = []
    for sc, ev in WANT.items():
        evs = got.get(sc, [])
        print(f'{sc}: {evs}')
        if not any(e == ev and s == 1 for e, s in evs): bad.append(f'{sc}: нет реплики «{ev}»')
        if sc == 'pedhit' and evs and evs[0][0] == 'near': bad.append('pedhit: «чуть не» перед ударом')
    if bad:
        print(('КРАСНЫЙ (ожидаемо): ' if red else 'ПРОВАЛ: ') + '; '.join(bad)); return 0 if red else 1
    if red: print('ПРОВАЛ ГЕЙТА: красный прогон прошёл'); return 1
    print('OK: голоса улицы звучат на своих событиях'); return 0


def run(eboot, negative):
    import common as C, port as PT
    scen = (ROOT / 'tests/traffic/streetvoice_scenario.txt').read_text()
    if negative: scen = 'flag streetvoff\n' + scen
    d, man = PT.stage_full(C.OUT / 'scen', 'streetvoice' + ('_red' if negative else ''), scen, 5)
    if eboot: (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(PT.HEADLESS), '--graphics=software', '--timeout=300', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        PT.watch_no_window(pr, 360)
    print(f'прогон: {d.relative_to(ROOT)} (EBOOT {C.sha256(d / "EBOOT.PBP", 16)})')
    return d / 'smoke.txt'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--eboot'); ap.add_argument('--negative', action='store_true'); ap.add_argument('--check'); a = ap.parse_args()
    smoke = Path(a.check) if a.check else run(a.eboot, a.negative)
    return check(smoke, a.negative)


if __name__ == '__main__':
    sys.exit(main())
