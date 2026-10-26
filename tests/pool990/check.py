#!/usr/bin/env python3
# №990: счёт POOL990 из smoke.txt. check.py smoke.txt [--default]   последняя строка PASS/FAIL
#  пары (stills.txt): строки идут парами «0 (TEST70), 1 (новое)» с одной камерой. В паре, где у прежнего есть конусы: у прежнего эллипсы есть (счёт живой), у нового эллипсов 0,
#     конусов столько же (±5 % и ±2): конус на месте. Таких пар не меньше 4 (уровни с конусами: L1, L3, L4, L5, L6 причал, L7 ночь)
#  --default (defaults.txt, ни одной строки flag pool990): все строки on=1, эллипсов нигде нет, конусы где-то рисуются. Прежний движок (POOL990_OLD=1) обязан здесь упасть
import sys, re
rows = []
for l in open(sys.argv[1], errors='ignore'):
    m = re.match(r'POOL990 level=(\d+) on=(\d) ell_tab=(\d+) ell_cell=(\d+) cone_tab=(\d+) cone_cell=(\d+)', l)
    if m: rows.append(tuple(int(x) for x in m.groups()))
ok = True
if not rows: print('нет строк POOL990'); ok = False
if '--default' in sys.argv:
    for L, on, et, ec, ct, cc in rows:
        bad = on != 1 or et or ec
        print(f'L{L}: on={on} эллипсов {et + ec}, конусов {ct + cc}' + (' <- ЭЛЛИПСЫ ИЛИ ВЫКЛЮЧЕНО' if bad else ''))
        if bad: ok = False
    if sum(r[4] + r[5] for r in rows) == 0: print('конусов нигде нет'); ok = False
else:
    pairs = 0
    for i in range(0, len(rows) - 1, 2):
        a, b = rows[i], rows[i + 1]
        co, cn = a[4] + a[5], b[4] + b[5]; eo, en = a[2] + a[3], b[2] + b[3]
        bad = []
        if a[1] != 0 or b[1] != 1: bad.append('порядок 0,1 нарушен')
        if co > 0:
            pairs += 1
            if eo == 0: bad.append('у прежнего эллипсов нет (счёт мёртвый)')
            if en: bad.append('у нового остались эллипсы')
            if abs(cn - co) > 0.05 * co + 2: bad.append('конусов не столько же')
        print(f'L{a[0]}: прежнее эллипсов {eo}, конусов {co}; новое эллипсов {en}, конусов {cn}' + (' <- ' + ', '.join(bad) if bad else ''))
        if bad: ok = False
    if pairs < 4: print(f'пар с конусами {pairs} (нужно не меньше 4)'); ok = False
print('PASS' if ok else 'FAIL')
