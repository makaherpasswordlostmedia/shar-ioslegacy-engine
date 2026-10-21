#!/usr/bin/env python3
"""Гейт данных: квады свечения анимированных объектов уровня (AnimCollision 0x3F00008 / Anim 0x3F0000C, tools/animobj_export.py)
стоят там, где их рисует оригинал, и пульсируют своей анимацией BQG.

  python3 tests/levelmech/animobj_bills_check.py [--levels 1-7]

Почему (04.10, «подтяни все объекты миссий», запись PS2 10:02–10:05): красное пульсирующее кольцо вокруг выключателя
грузовика Duff (Anim z2switchbbqgrp в l1z2/l4z2/l7z2), голубые кольца звонков (switchN_bb рядом с DB_*), огни пульта АЭС
(z6_switchlights) и др. — типы SPR1 без кусков. Было две ошибки экспорта:
  1. коробка кусков пустая -> экземпляр вставал в (0, 0.5, 0), а движок отсекает экземпляр по его центру
     (viewer/stateprops.c spDrawable, 60 м) — кольца не рисовались нигде (красный: AO_BILL_CENTER_OLD=1);
  2. суставы стоят (PTRN без движения) -> у типа 0 кадров, кадр не идёт, дорожка BQG (ширина, цвет, альфа по кадрам) стоит
     на кадре 0: кольцо выключателя маленькое (1.04 м) и почти прозрачное (альфа 0.13), не пульсирует (красный:
     AO_BILL_FRAMES_OLD=1).
Проверка (экспорт без конвертера: меши — треугольник-заглушка, как tests/levelmech/barriers_check.py):
  * у каждого типа объекта с квадами центр каждой группы квадов (поза кадра 0, мир = экземпляр + сустав) ближе REACH м
    к центру экземпляра по xz;
  * у каждого типа, где у квада дорожка BQG длиннее 1 кадра, а действия нет, — состояние крутит кадр по кругу и кадров
    не меньше длины дорожки;
  * уровень 1: кольцо выключателя Duff z2switchbbqgrp стоит у выключателя (203.2, 5.0, 293.0 ± 0.5 м) и пульсирует.
"""
import argparse, contextlib, io, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools'))
REACH = 30.0                                 # = animobj_export.CLUSTER: части дальше — отдельный экземпляр
DUFF_RING = ('z2switchbbqgrp', (203.17, 5.0, 293.0))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--levels', default='1-7'); a = ap.parse_args()
    lo, _, hi = a.levels.partition('-'); levels = range(int(lo), int(hi or lo) + 1)
    import prp2_export as PX, animobj_export as AX
    art = ROOT / 'hit-and-run-web/source/game/art'
    tri = [(0, 0, np.eye(3), np.zeros((3, 2)), np.full(3, 0xffffffff, np.uint32))]
    fails, nb_types, nb_bills, nb_anim = [], 0, 0, 0
    for lv in levels:
        with contextlib.redirect_stdout(io.StringIO()):
            sp = PX.StateProps(lv, art, lambda f, m: tri, lambda f, s: (0, 2), verbose=False)
            ao = AX.AnimObjects(lv, art, sp, None, verbose=False)
        seen = []
        for o in ao.objs:
            for ti in o['types']:
                T = sp.types[ti]
                if not T['bills']: continue
                c = np.asarray(T['inst'][0][0][3, :3], np.float64); JW = PX.rest_world(T['joints'])
                grp = {}                     # группа квадов 0x17002 (часть рисунка) — целиком в одном экземпляре
                for b in T['bills']:
                    M = JW[b['joint']] if b['joint'] < len(JW) else np.eye(4)
                    grp.setdefault(b['name'], []).append((M @ np.append(np.asarray(b['t'], np.float64), 1.0))[:3] + c)
                wp = [np.mean(v, 0) for v in grp.values()]
                far = max(float(np.hypot(*(p - c)[[0, 2]])) for p in wp)
                nb_types += 1; nb_bills += len(T['bills'])
                ntr = max(len(b['track']) for b in T['bills'])
                pose = T['states'][0]['pose']
                spins = pose[0] == 2 and T['nfr'] >= ntr
                seen.append((T['name'], c, np.mean(wp, 0), far, len(T['pieces']), ntr, spins))
                if far > REACH:
                    fails.append(f"L{lv} {T['name']}: группа квадов в {far:.0f} м от центра экземпляра {np.round(c, 1)} "
                                 f"(квады у {np.round(np.mean(wp, 0), 1)}, кусков {len(T['pieces'])})")
                if ntr > 1 and not o['action'] and o['loop'] == 1:
                    nb_anim += 1
                    if not spins:
                        fails.append(f"L{lv} {T['name']}: дорожка BQG {ntr} кадров, а кадр типа стоит (кадров {T['nfr']}, поза {pose[:3]})")
        only = [s for s in seen if not s[4]]
        print(f'L{lv}: типов с квадами {len(seen)}, из одних квадов {len(only)}: ' +
              ', '.join(f'{n} {np.round(w, 1).tolist()}{" пульс" if sp_ else ""}' for n, c, w, _, _, _, sp_ in only[:6]) +
              (' …' if len(only) > 6 else ''))
        if lv == 1:
            ring = [s for s in seen if s[0] == DUFF_RING[0]]
            if not ring: fails.append(f'L1: нет типа {DUFF_RING[0]} (кольцо выключателя грузовика Duff)')
            else:
                n, c, w, _, _, ntr, spins = ring[0]
                if np.linalg.norm(w - np.asarray(DUFF_RING[1])) > .5 or np.hypot(*(c - np.asarray(DUFF_RING[1]))[[0, 2]]) > .5:
                    fails.append(f'L1 {n}: центр {np.round(c, 2)} / квады {np.round(w, 2)} не у выключателя {DUFF_RING[1]}')
                if not spins: fails.append(f'L1 {n}: кольцо не пульсирует (дорожка {ntr} кадров)')
    for f in fails: print('  FAIL', f)
    print(f'итого: типов с квадами {nb_types}, квадов {nb_bills}, с анимацией BQG без действия {nb_anim}, ошибок {len(fails)}')
    print('PASS' if not fails else 'FAIL')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
