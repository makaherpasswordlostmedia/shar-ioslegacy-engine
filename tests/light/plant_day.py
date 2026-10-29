#!/usr/bin/env python3
"""Подложенный «день» для гейта света (29.09, рецепт §12): level.shr уровня N со светом уровня, но машина и персонажи — в
дневном свете уровня 1. Всё прочее (город, CAR1: машина уровня, камера, кузов) — побайтно как в настоящем файле, поэтому в
эмуляторе отличается только свет.

  plant_day.py НОВЫЙ.shr ДЕНЬ.shr > ВЫХОД.shr     (ДЕНЬ — тот же уровень, собранный до света уровня: *_pre_light.shr)
Что меняется: цвет вершин кусков машины (owner 1) — из файла ДЕНЬ (куски сверяются по порядку, числу вершин и флагам; не
сошлись — отказ), версия CAR1 3 -> 2 (блок LGT1 движок не читает — персонажам свет уровня 1)."""
import struct, sys
from pathlib import Path


def pieces(b):
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    out = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        fl, nv, ni, own = r[7:11]; off, nf, ci = r[15:18]
        if own == 1: out.append((fl, nv, ni, nf, r[18], r[19], cells[ci][9] + off))
    return out


def main():
    new, day = bytearray(Path(sys.argv[1]).read_bytes()), Path(sys.argv[2]).read_bytes()
    A, B = pieces(new), pieces(day)
    if len(A) != len(B): sys.exit(f'кусков машины {len(A)} и {len(B)} — не один и тот же экспорт машины')
    n = 0
    for (fa, nva, nia, nfa, ja, va, oa), (fb, nvb, nib, nfb, jb, vb, ob) in zip(A, B):
        if (fa, nva, nia, nfa, ja, va) != (fb, nvb, nib, nfb, jb, vb): sys.exit('куски машины не совпали по флагам/вершинам/суставу')
        if not fa & 16: sys.exit('кусок машины с индексами — не поддержан')
        vs = 12 if fa & 32 else 16; cw = 2 if vs == 12 else 4
        for k in range(nva):
            new[oa + k * vs + 4:oa + k * vs + 4 + cw] = day[ob + k * vs + 4:ob + k * vs + 4 + cw]
            # геометрия обязана совпасть (иначе это разные машины)
            if new[oa + k * vs + (6 if vs == 12 else 8):oa + (k + 1) * vs - (0 if vs == 12 else 2)] != \
               day[ob + k * vs + (6 if vs == 12 else 8):ob + (k + 1) * vs - (0 if vs == 12 else 2)]: sys.exit('геометрия куска машины отличается')
        n += nva
    c1, = struct.unpack_from('<I', new, 100)
    if new[c1:c1 + 4] != b'CAR1': sys.exit('нет CAR1')
    struct.pack_into('<I', new, c1 + 4, 2)
    sys.stdout.buffer.write(bytes(new))
    print(f'дневной свет подложен: {len(A)} кусков машины, {n} вершин; CAR1 v2 (LGT1 не читается)', file=sys.stderr)


if __name__ == '__main__':
    main()
