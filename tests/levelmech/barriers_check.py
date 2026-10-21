#!/usr/bin/env python3
"""Гейт данных: барьеры 0x3F0000F (AnimDynamicPhysicsWrapper) уровней 1–7 -> типы SPR1 (tools/prp2_export.py _add_animphys).

  python3 tests/levelmech/barriers_check.py [--levels 1-7] [--swap-atc] [--half X]

Всё сверяется с диском Роба (read-only), экспорт — без конвертера (меши подменены треугольником: проверяется машина
состояний, огни, объёмы, обломок, экземпляры, а не геометрия). На каждый уровень:
  1. барьеров-типов и экземпляров = сущностей 0x3F0000E с обёрткой 0x3F0000F и их InstanceList на диске (без дублей точек);
  2. у каждого огня (квадрат с каналом CLR) есть кадры «горит» и «не горит» — мигает; огни типа не все одинаковые
     (попеременно, как ключи CLR); огни — в своих слотах с флагом PVIS; клип типа = длина главного контроллера 0x48A0;
  3. объёмов коллизии >= 1; меш барьера убран из города (иначе рисовался бы дважды);
  4. удар (VEHICLE_HIT и HIT) -> состояние с вызовами BREAK(n), COLOFF, REMOVE; n = номер обломка строки ATC сущности, и
     обломок n на уровне построен и по содержимому тот: у барьера donotenter — частицы *donotenter*, у переезда — *crossing*.
Отрицательные контроли (гейт tests/levelmech/barriers.sh): SHR_NO_ANIMPHYS=1 (как до 29.09), --swap-atc (номера обломков
перепутаны), --half 1.1 (огонь никогда не горит) — каждый обязан дать FAIL.
"""
import argparse, os, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--levels', default='1-7')
    ap.add_argument('--swap-atc', action='store_true', help='подложить перепутанные номера обломков (красный)')
    ap.add_argument('--half', type=float, help='подложить порог яркости огня (красный при > 1)')
    a = ap.parse_args()
    lo, _, hi = a.levels.partition('-'); levels = range(int(lo), int(hi or lo) + 1)
    import prp2_export as PX
    from p3d import read, walk, string
    if a.swap_atc:
        PX.BREAK_BY_ATC['eBigBarrierBreaking'], PX.BREAK_BY_ATC['eRailCrossBreaking'] = 17, 16
    if a.half is not None: PX.ANIMPHYS_HALF = a.half
    art = ROOT / 'hit-and-run-web/source/game/art'
    tri = [(0, 0, np.eye(3), np.zeros((3, 2)), np.full(3, 0xffffffff, np.uint32))]
    fails, total = [], 0

    def bad(msg): fails.append(msg); print('  FAIL', msg)

    for lv in levels:
        # диск: барьеры и экземпляры
        want = {}
        for f in PX.level_files(art, lv):
            for ent in read(f).children:
                if ent.id != 0x3f0000e or not any(c.id == 0x3f0000f for c in ent.children): continue
                if any(c.id == 0x3f00010 for c in ent.children): continue
                pts = {tuple(np.round(M[3, :3], 2)) for _, M in PX.inst_list(ent)}
                want.setdefault(string(ent.data)[0], set()).update(pts)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            sp = PX.StateProps(lv, art, lambda f, m: tri, lambda f, s: -1, verbose=False)
        got = {T['name']: T for T in sp.types if 'animphys' in T}
        print(f'L{lv}: на диске барьеров {len(want)} ({sum(len(v) for v in want.values())} шт.), в SPR1 {len(got)}')
        if set(got) != set(want): bad(f'L{lv}: типы {sorted(got)} != диск {sorted(want)}')
        brk_types = {T['bindex']: T for T in sp.types if T['kind'] == 1}
        for name, T in got.items():
            total += 1
            n_inst = len(T['inst'])
            if n_inst != len(want.get(name, ())): bad(f'{name}: экземпляров {n_inst}, на диске {len(want.get(name, ()))}')
            ap_ = T['animphys']
            lights = [b for b in T['bills'] if b.get('pvis')]
            if len(lights) < 2: bad(f'{name}: огней {len(lights)} < 2')
            if T['nfr'] != ap_['frames'] or not T['nfr']: bad(f'{name}: кадров клипа {T["nfr"]}, контроллер {ap_["frames"]}')
            patt = []
            for b in lights:
                bit = 1 << b['slot']
                if not (T['pvis_mask'] & bit): bad(f'{name}: огонь слота {b["slot"]} не в PVIS')
                seq = tuple(int(bool(m & bit)) for m in T['vis_frames'])
                patt.append(seq)
                if not (any(seq) and not all(seq)): bad(f'{name}: огонь слота {b["slot"]} не мигает ({sum(seq)}/{len(seq)} кадров горит)')
            if patt and len(set(patt)) < 2: bad(f'{name}: все огни горят одинаково (нет попеременного мигания)')
            if not T['cols']: bad(f'{name}: нет объёма коллизии')
            mesh_names = [p for p, _, _ in T['props'] if not p.endswith('bbShape') and 'bb' not in p]
            if not any(m in sp.city_skip for m in mesh_names): bad(f'{name}: меш {mesh_names} остался в городе')
            st = T['states']
            ev = dict((e, to) for e, to in st[0]['events'])
            if ev.get(PX.EV['VEHICLE_HIT']) != 1 or ev.get(PX.EV['HIT']) != 1 or len(st) < 2:
                bad(f'{name}: удар машины/пинок не ведут в обломок ({st[0]["events"]})'); continue
            calls = [(op, arg) for op, arg, _ in st[1]['calls']]
            brk = next((arg for op, arg in calls if op == PX.OP_BREAK), None)
            if (PX.OP_COLOFF, 0) not in calls or (PX.OP_REMOVE, 0) not in calls or brk is None:
                bad(f'{name}: вызовы обломка {calls}')
            B = brk_types.get(brk)
            if B is None: bad(f'{name}: обломок {brk} на уровне не построен'); continue
            want_word = 'donotenter' if 'donotenter' in name else 'crossing' if 'railcross' in name else ''
            parts = [p for p, _, _ in B['props']] + [e for e, _ in B['effects']]
            if want_word and not any(want_word in p.lower() for p in parts):
                bad(f'{name}: обломок {brk} не тот по содержимому ({parts[:4]})')
            on = [sum(s) for s in patt]
            print(f'  {name}: x{n_inst}, огней {len(lights)}, {T["nfr"]} кадров @{T["fps"]:g}, горит {on}, объёмов {len(T["cols"])}, '
                  f'обломок {brk} ({parts[0] if parts else "-"}), масса {T["mass"]:g}')
    print(f'барьеров-типов проверено: {total}')
    if total == 0 and any(lv in (2, 5) for lv in levels): bad('на уровнях 2/5 нет ни одного барьера')
    print('RESULT:', 'FAIL' if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
