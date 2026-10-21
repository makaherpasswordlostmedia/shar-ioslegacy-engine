#!/usr/bin/env python3
"""Гейт: летающие актёры не-осы (AddFlyingActorByLocator, уровень 7 — корабль и его луч UFO_BEAM_ALWAYS_ON) в игре.

  python3 tests/levelmech/flying_check.py --level N --shr LEVEL.shr --collect collect-lN.shr [--homer build/homer.shr]

Ожидание — только с диска Роба: актёры из leveli.mfk уровня (не beecamera), их локатор (p3d уровня и миссий), рисунки
поведений UFO_BEAM_ALWAYS_ON. Игра — tests/levelmech/lvmech --actors (настоящий код: world.c, collect.c, stateprops.c,
2 с игры). PASS, если на каждого актёра с диска в игре есть экземпляр корабля и экземпляр луча на его локаторе (±0,05 м),
живые; у корабля коллизия снята (s0 данных: REMOVE_COLLISION_VOLUME) и видны куски; луч в состоянии покоя (s1 после авто-
перехода 1 с) и виден хотя бы один билборд >= 10 м; лишних экземпляров нет. Уровни без актёров — 0 экземпляров.
Отрицательные контроли гейта: пакет без актёров (прежний экспорт) и пакет со сдвинутым на 5 м экземпляром.
"""
import argparse, subprocess, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/missions')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))


def disk_actors(level):
    import mfk, p3dlocs
    game = ROOT / 'hit-and-run-web/source/game'
    calls, _ = mfk.parse((game / f'scripts/missions/level0{level}/leveli.mfk').read_text(errors='replace'), 'leveli.mfk')
    beams = {str(c.args[0]) for c in calls if c.op == 'AddBehaviour' and len(c.args) >= 3 and str(c.args[1]).upper() == 'UFO_BEAM_ALWAYS_ON'}
    want = []
    files = sorted((game / f'art/missions/level0{level}').glob('*.p3d')) + sorted((game / 'art').glob(f'l{level}*.p3d'))
    for c in calls:
        if c.op != 'AddFlyingActorByLocator' or len(c.args) < 3 or str(c.args[0]).lower() == 'beecamera': continue
        loc = str(c.args[2]); pos = None
        for f in files:
            locs, _ = p3dlocs.read_locators(f, f.name)
            L = next((l for l in locs if l.name == loc), None)
            if L is not None: pos = L.pos; break
        want.append(dict(name=str(c.args[1]), loc=loc, pos=pos, beam=str(c.args[1]) in beams))
    return want


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, required=True)
    ap.add_argument('--shr', required=True)
    ap.add_argument('--collect', required=True)
    ap.add_argument('--homer', default=str(Path('/Users/USER/Downloads/shar-psp/build/homer.shr')))
    ap.add_argument('--bin', default=str(ROOT / 'build/levelmech/lvmech'))
    a = ap.parse_args()
    want = disk_actors(a.level)
    env = dict(os.environ, BW_NO_TRAFFIC='1', BW_NO_ROOMS='1', BW_LEVEL=str(a.level), BW_COLLECT=a.collect)
    out = subprocess.run([a.bin, a.shr, a.homer, '--actors'], env=env, capture_output=True, text=True).stdout
    got = []
    for ln in out.splitlines():
        if not ln.startswith('A\t'): continue
        f = ln.split('\t')
        got.append(dict(i=int(f[1]), pos=tuple(map(float, f[2].split())), state=int(f[3]), alive=int(f[4]), col=int(f[5]),
                        bills=int(f[6]), big=float(f[7]), pieces=int(f[8])))
    print(f'L{a.level}: на диске летающих актёров {len(want)} ' + ' '.join(f"{w['name']}@{w['loc']}{'+луч' if w['beam'] else ''}" for w in want)
          + f'; в игре экземпляров {len(got)}')
    fails = []
    need = sum(1 + w['beam'] for w in want)
    if len(got) != need: fails.append(f'экземпляров {len(got)}, по диску {need}')
    for w in want:
        if w['pos'] is None: fails.append(f"{w['name']}: локатора {w['loc']} нет на диске"); continue
        near = [g for g in got if max(abs(g['pos'][k] - w['pos'][k]) for k in range(3)) <= 0.05]
        ship = next((g for g in near if g['pieces'] > 0), None)
        beam = next((g for g in near if g['bills'] > 0 and g['big'] >= 10.0), None)
        print(f"  {w['name']}: локатор {tuple(round(v, 2) for v in w['pos'])}; рядом в игре {len(near)}: "
              + '; '.join(f"#{g['i']} сост {g['state']} жив {g['alive']} колл {g['col']} кусков {g['pieces']} билб {g['bills']} ({g['big']:.1f} м)" for g in near))
        if ship is None or not ship['alive']: fails.append(f"{w['name']}: корабля на локаторе нет")
        elif ship['col']: fails.append(f"{w['name']}: у корабля коллизия не снята")
        if w['beam'] and (beam is None or beam['state'] != 1): fails.append(f"{w['name']}: луча на локаторе нет или не в покое s1")
    for f in fails: print('  FAIL', f)
    print('RESULT:', 'FAIL' if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
