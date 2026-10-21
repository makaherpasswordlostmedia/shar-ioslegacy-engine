#!/usr/bin/env python3
"""Чем отличается level.shr с машиной в CAR1 v2 от прежнего (уровень 1 обязан отличаться только этим, 29.09).

  shr_diff.py СТАРЫЙ НОВЫЙ     PASS / FAIL: всё до CAR1 побайтно то же (кроме смещения PVS1 @88), CAR1 = прежняя секция
                               + версия 2, смещение и длина блока машины (@24, @28) + блок машины в конце; всё после CAR1 (PVS1
                               и хвост) побайтно то же."""
import struct, sys
from pathlib import Path


def main():
    a, b = Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes()
    pa, ca = struct.unpack_from('<I', a, 88)[0], struct.unpack_from('<I', a, 100)[0]
    pb, cb = struct.unpack_from('<I', b, 88)[0], struct.unpack_from('<I', b, 100)[0]
    bad = []
    if ca != cb: bad.append(f'CAR1 сдвинулась: {ca} -> {cb}')
    if not (ca < pa and cb < pb): bad.append('PVS1 не после CAR1')
    ha, hb = bytearray(a[:ca]), bytearray(b[:cb]); ha[88:92] = hb[88:92] = b'\0\0\0\0'
    if ha != hb: bad.append(f'до CAR1 отличается ({sum(x != y for x, y in zip(ha, hb))} Б)')
    A, B = a[ca:pa], bytearray(b[cb:pb])
    vb, io, il = struct.unpack_from('<I', B, 4)[0], *struct.unpack_from('<2I', B, 24)
    old = bytearray(A); body = bytearray(B[:io])
    struct.pack_into('<I', body, 4, 1); struct.pack_into('<2I', body, 24, 0, 0)
    if vb != 2 or bytes(body) != bytes(old):
        bad.append('CAR1 отличается не только блоком машины')
    if a[pa:] != b[pb:]: bad.append('PVS1 и хвост отличаются')
    print(f'CAR1 {len(A)} -> {len(B)} Б (блок машины {il} Б @{io}), PVS1 {pa} -> {pb}; размер {len(a)} -> {len(b)}')
    for x in bad: print('  ПРОВАЛ:', x)
    print('PASS' if not bad else 'FAIL'); return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
