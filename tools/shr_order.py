#!/usr/bin/env python3
"""Загрузка 2, пункт 3: порядок секций level.shr «одним проходом».

Было: [резидент..клеточная таблица][блобы клеток 13-17 МБ][COL1][PRP2][CAR1][REG1+REGF][PVS1]
Стало: [резидент..клеточная таблица][COL1][PRP2][CAR1][REG1+REGF][PVS1][блобы клеток]
Загрузка читает резидент и хвост (COL1, PRP2, CAR1, PVS1, REG1) подряд без прыжков через клетки; клетки круга идут за ними.
Меняется только место блоков: заголовок @88 pvs, @92 col, @96 prop, @100 car уменьшаются на размер клеток, смещения блобов в клеточной
таблице (@36 каждой записи по 48 Б) растут на размер хвоста, 'at' в REGF-сноске уменьшается на размер клеток. Содержимое секций не трогается.
  tools/shr_order.py LEVEL.shr [OUT.shr]      на месте или в OUT; уже в новом порядке — ничего не делает
  tools/shr_order.py LEVEL.shr --check        0 — в новом порядке и согласовано
SHR_ORDER_OLD=1 в tools/build_level.sh — шаг пропускается."""
import struct, sys

def parse(d):
    if d[:4] != b'SHR7': raise SystemExit('shr_order: не SHR7')
    tableOff, ncell, cellOff, pvs, col, prop, car = struct.unpack_from('<7I', d, 76)
    return tableOff, ncell, cellOff, pvs, col, prop, car

def main():
    a = sys.argv[1:]
    if not a: raise SystemExit(__doc__)
    path = a[0]; check = '--check' in a; out = next((x for x in a[1:] if not x.startswith('--')), path)
    d = bytearray(open(path, 'rb').read())
    tableOff, ncell, cellOff, pvs, col, prop, car = parse(d)
    resEnd = cellOff + 48 * ncell
    offs = [struct.unpack_from('<I', d, cellOff + 48 * i + 36)[0] for i in range(ncell)]
    sizes = [struct.unpack_from('<I', d, cellOff + 48 * i + 40)[0] for i in range(ncell)]
    cmin = min(offs) if ncell else resEnd; cmax = max(o + s for o, s in zip(offs, sizes)) if ncell else resEnd
    if col <= cmin:   # новый порядок: хвост сразу за резидентом
        tail_end = min(offs) if ncell else len(d)
        ok = col == resEnd and cmin >= max(pvs, col) and cmax <= len(d)
        print('shr_order: уже в новом порядке' if ok else 'shr_order: НЕ согласовано (col=%d resEnd=%d cmin=%d)' % (col, resEnd, cmin))
        raise SystemExit(0 if ok else 1)
    if check: print('shr_order: старый порядок (клетки %d..%d перед COL1 %d)' % (cmin, cmax, col)); raise SystemExit(1)
    # проверка старого порядка: клетки вплотную за резидентом и до COL1, хвост до конца файла
    if cmin < resEnd or cmax > col or resEnd > col: raise SystemExit('shr_order: неожиданная раскладка (resEnd=%d cells=%d..%d col=%d)' % (resEnd, cmin, cmax, col))
    C = col - resEnd; T = len(d) - col
    # REGF-сноска: прямо перед PVS1 (а без PVS — последние 16 Б файла)
    end = pvs if pvs else len(d)
    regf = end - 16
    new = bytearray(d[:resEnd]) + d[col:] + d[resEnd:col]
    for h in (88, 92, 96, 100):
        v = struct.unpack_from('<I', new, h)[0]
        if v: struct.pack_into('<I', new, h, v - C)
    if new[regf - C:regf - C + 4] == b'REGF':
        at = struct.unpack_from('<I', new, regf - C + 4)[0]; struct.pack_into('<I', new, regf - C + 4, at - C)
    for i in range(ncell):
        p = cellOff + 48 * i + 36; v = struct.unpack_from('<I', new, p)[0]; struct.pack_into('<I', new, p, v + T)
    assert len(new) == len(d)
    open(out, 'wb').write(new)
    print('shr_order: клетки %d Б перенесены за хвост %d Б; COL1 теперь @%d' % (C, T, struct.unpack_from('<I', new, 92)[0]))

main()
