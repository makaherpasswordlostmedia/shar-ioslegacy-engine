#!/usr/bin/env python3
"""Гейт Г5/П4 (1): цели ботов «карточка» и «оса» = игровые объекты уровня, как в паспорте (tools/level/passport.py collectibles:
карточки — action-локаторы CollectorCard с номером из данных, осы — AddSpawnPointByLocatorScript из leveli.mfk).
  check.py TARGETS.tsv [--level 1]  -> PASS/FAIL построчно; код 0 только если число, имена и места (±0.05 м) совпали."""
import argparse, io, contextlib, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/level'))
import passport as PP


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('targets'); ap.add_argument('--level', type=int, default=1)
    a = ap.parse_args()
    with contextlib.redirect_stdout(io.StringIO()):
        col = PP.collectibles(a.level, PP.level_locators(a.level))
    want = {'card': {c['data']: c['pos'] for c in col['cards']}, 'wasp': {w['loc']: w['pos'] for w in col['wasps']}}
    got = {'card': {}, 'wasp': {}}
    for l in Path(a.targets).read_text().splitlines():
        f = l.split('\t')
        if f[0] in got: got[f[0]][f[1]] = [float(v) for v in f[2].split()]
    bad = 0
    for k in ('card', 'wasp'):
        W, G = want[k], got[k]
        miss, extra = sorted(set(W) - set(G)), sorted(set(G) - set(W))
        moved = [n for n in set(W) & set(G) if max(abs(x - y) for x, y in zip(W[n], G[n])) > .05]
        ok = len(G) == len(W) and not miss and not extra and not moved
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'} {k}: ботов {len(G)}, паспорт {len(W)}" + (f'; нет {miss}' if miss else '') +
              (f'; лишние {extra}' if extra else '') + (f'; не на месте {sorted(moved)}' if moved else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
