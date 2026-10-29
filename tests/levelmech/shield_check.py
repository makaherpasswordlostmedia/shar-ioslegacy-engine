#!/usr/bin/env python3
"""Гейт щитов ос (AddShield) на уровне N: ожидание с диска Роба, игра — tests/levelmech/lvmech --shield (настоящий код world.c,
collect.c, stateprops.c).

  python3 tests/levelmech/shield_check.py --level N --shr LEVEL.shr --collect collect-lN.shr [--ntest 3]

Диск: leveli.mfk уровня — AddShield("beecamera", рисунок) есть (уровни 5–7) или нет, и сколько ос (AddSpawnPointByLocatorScript).
PASS: щит у стольких ос, сколько на диске (все при AddShield, ни одной без); у проверенных ос удары пинком — щит держит, пролом,
третий удар убивает осу, щит гаснет (правило порта COLL_SHIELD_HP = 2); машина на газу бьёт щит, не осу; без AddShield — первый
удар убивает. Отрицательные контроли гейта: пакет без щитов (прежний экспорт), сборка -DCOLL_SHIELD_ON=0.
"""
import argparse, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/missions'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, required=True); ap.add_argument('--shr', required=True); ap.add_argument('--collect', required=True)
    ap.add_argument('--homer', default='/Users/USER/Downloads/shar-psp/build/homer.shr')
    ap.add_argument('--bin', default=str(ROOT / 'build/levelmech/lvmech')); ap.add_argument('--ntest', type=int, default=3)
    a = ap.parse_args()
    import mfk
    calls, _ = mfk.parse((ROOT / f'hit-and-run-web/source/game/scripts/missions/level0{a.level}/leveli.mfk').read_text(errors='replace'), 'leveli.mfk')
    has = any(c.op == 'AddShield' and len(c.args) >= 2 and str(c.args[0]).lower() == 'beecamera' for c in calls)
    nwasp = sum(1 for c in calls if c.op == 'AddSpawnPointByLocatorScript' and len(c.args) >= 6 and str(c.args[1]).lower() == 'beecamera')
    env = dict(os.environ, BW_NO_TRAFFIC='1', BW_NO_ROOMS='1', BW_LEVEL=str(a.level), BW_COLLECT=a.collect)
    out = subprocess.run([a.bin, a.shr, a.homer, '--shield', str(a.ntest)], env=env, capture_output=True, text=True).stdout
    print(out.strip())
    m = re.search(r'ос (\d+), со щитом (\d+)', out)
    bad = []
    if not m: bad.append('нет строки ос/щитов')
    else:
        n, s = int(m.group(1)), int(m.group(2))
        want = n if has else 0
        print(f'диск: AddShield {"есть" if has else "нет"}, ос {nwasp}; в игре ос {n}, со щитом {s} (ждали {want})')
        if s != want: bad.append(f'щитов {s}, по диску {want}')
    if 'RESULT: PASS' not in out: bad.append('проверка ударов не прошла')
    for b in bad: print('  FAIL', b)
    print('RESULT:', 'FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
