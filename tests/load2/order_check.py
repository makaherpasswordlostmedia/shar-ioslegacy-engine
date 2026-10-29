#!/usr/bin/env python3
"""Гейт пункта 3 загрузки 2: level.shr в новом порядке (tools/shr_order.py) несёт ТЕ ЖЕ байты каждой секции, что исходный.
   order_check.py OLD.shr NEW.shr   -> 0 при совпадении; печатает по секциям. Отрицательный контроль: --plant (портит байт клетки в копии)"""
import struct, sys
def secs(d):
    tableOff, ncell, cellOff, pvs, col, prop, car = struct.unpack_from('<7I', d, 76)
    resEnd = cellOff + 48 * ncell
    cells = []; cells0 = [(0, 0, struct.unpack_from('<I', d, cellOff + 48 * i + 36)[0]) for i in range(ncell)]
    for i in range(ncell):
        r = d[cellOff + 48 * i: cellOff + 48 * i + 48]; off, sz = struct.unpack_from('<II', r, 36)
        cells.append((r[:36] + r[44:], bytes(d[off:off + sz])))   # запись без смещения/размера + блоб
    cmin = min(c[2] for c in cells0) if cells0 else len(d)
    regf = (pvs if pvs else len(d)) - 16
    at = struct.unpack_from('<I', d, regf + 4)[0] if d[regf:regf + 4] == b'REGF' else None
    ends = sorted(x for x in (pvs, prop, car, len(d)) if x > col)
    return dict(
        res_head=bytes(d[:4]) + bytes(d[4:76]), res_body=bytes(d[104:resEnd]) if False else None,
        resident_after_hdr=bytes(d[104:cellOff]),   # карта, стены, текстуры, таблица кусков — до клеточной таблицы
        cells=cells,
        col=bytes(d[col:min(x for x in (pvs, prop) if x > col)]),
        prop=bytes(d[prop:car]) if car > prop else bytes(d[prop:pvs]),
        car=bytes(d[car:(regf if d[regf:regf+4] == b'REGF' else pvs)]),
        regf_at=(at,), regfoot=bytes(d[regf:regf + 4]) + bytes(d[regf + 8:regf + 16]) if at is not None else b'',
        reg=(bytes(d[at:regf]) if at is not None else b''),
        pvs=bytes(d[pvs:(cmin if cmin > pvs else len(d))]) if pvs else b'', hdr_scalars=bytes(d[:76]), size=len(d))
def main():
    old = open(sys.argv[1], 'rb').read(); new = bytearray(open(sys.argv[2], 'rb').read())
    if '--plant' in sys.argv:   # красный: испортить байт первой непустой клетки
        cellOff = struct.unpack_from('<I', new, 84)[0]; off, sz = struct.unpack_from('<II', new, cellOff + 36); new[off + sz // 2] ^= 0xFF
    a, b = secs(old), secs(bytes(new)); bad = []
    for k in a:
        if k == 'regf_at': continue
        if a[k] != b[k]: bad.append(k)
    h = struct.unpack_from('<7I', new, 76)
    print('секции совпали: %s' % ('да' if not bad else 'НЕТ: ' + ','.join(bad)))
    print('порядок: col=%d prop=%d car=%d pvs=%d < клетки от %d' % (h[4], h[5], h[6], h[3], min(struct.unpack_from('<I', new, h[2] + 48 * i + 36)[0] for i in range(h[1]))))
    ok = not bad and h[4] < h[5] < h[6] < h[3] and h[3] < min(struct.unpack_from('<I', new, h[2] + 48 * i + 36)[0] for i in range(h[1]))
    print('ИТОГ', 'OK' if ok else 'FAIL'); sys.exit(0 if ok else 1)
main()
