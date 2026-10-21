#!/usr/bin/env python3
"""Гейт «трафик уровня» (29.09): пакет TRF1 уровня N (build/levels/l<N>/traffic.shr, у уровня 1 — build/traffic.shr,
tools/traffic_export.py --level N) собран из СВОЕГО leveli.mfk: машины трафика = AddTrafficModel группы CreateTrafficGroup
(+ остов huskA последней моделью), модели пешеходов = все AddPed групп CreatePedGroup. Номера уровня в TRF1 нет — до
29.09 песочница писала «принадлежность не проверяется»; теперь принадлежность видна по составу.
  traffic_level_check.py --level N [N ...] [--traffic P]    PASS / FAIL
  traffic_level_check.py --level 3 --traffic build/levels/l1/traffic.shr    красный: трафик уровня 1 на уровне 3"""
import argparse, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/missions'))
import mfk   # noqa: E402

SCR = ROOT / 'hit-and-run-web/source/game/scripts/missions'


def trf_models(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'TRF1', path
    f = struct.unpack_from('<35I', b, 12)
    nmodel, offmodel, nped, offped = f[8], f[9], f[27], f[28]
    name = lambda o: b[o:o + 16].split(b'\0')[0].decode().lower()
    return [name(offmodel + 128 * i) for i in range(nmodel)], [name(offped + 32 * i) for i in range(nped)]


def want(lv):
    cmds, _ = mfk.parse((SCR / f'level{lv:02d}/leveli.mfk').read_text(errors='replace'))
    cars = [str(c.args[0]).lower()[:15] for c in cmds if c.op == 'AddTrafficModel' and c.args]
    peds = sorted({str(c.args[0]).lower()[:15] for c in cmds if c.op == 'AddPed' and c.args})
    return list(dict.fromkeys(cars)), peds


def default_traffic(lv):
    return next(p for p in ([ROOT / 'build/traffic.shr'] if lv == 1 else []) + [ROOT / f'build/levels/l{lv}/traffic.shr'] if p.exists())


def check(lv, path=None):
    path = path or default_traffic(lv)
    cars, peds = trf_models(path); wc, wp = want(lv)
    got_cars = cars[:-1] if cars and cars[-1].startswith('husk') else cars
    bad = []
    if got_cars != wc: bad.append(f'уровень {lv}: машины трафика {got_cars} != leveli.mfk {wc}')
    if sorted(set(peds)) != wp: bad.append(f'уровень {lv}: пешеходы {sorted(set(peds))} != leveli.mfk {wp}')
    print(f'уровень {lv}: машины {got_cars} (+ {cars[-1] if cars else "-"}), пешеходов {len(set(peds))} — '
          + ('как в leveli.mfk' if not bad else 'НЕ как в leveli.mfk'))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, nargs='+', required=True); ap.add_argument('--traffic')
    a = ap.parse_args()
    bad = [x for lv in a.level for x in check(lv, a.traffic)]
    for x in bad: print('ПРОВАЛ:', x[:300])
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
