#!/usr/bin/env python3
"""Сверка файла в полосах (tools/strips) со списком: у каждого куска те же треугольники с тем же обходом (вершины побайтно), прочее без изменений.
python3 -I tools/strips_check.py LIST.shr STRIPS.shr [--red]   (--red: красный контроль, портит один байт вершины в копии: сверка обязана упасть)"""
import struct, sys
from collections import Counter
F_STRIP = 1 << 26
def load(p):
    d = open(p, 'rb').read(); assert d[:4] == b'SHR7'
    npc, = struct.unpack_from('<I', d, 8); t, nc, co = struct.unpack_from('<III', d, 76)
    R = [struct.unpack_from('<6fiIIII4f IIIII', d, t + 80 * i) for i in range(npc)]   # bb6, tex, flags, nv, ni, owner, ox,oy,oz,sc, off, nf, cell, pad0, pad1
    C = [struct.unpack_from('<6fIIIIII', d, co + 48 * i) for i in range(nc)]
    return d, R, C
def norm(t): i = min(range(3), key=lambda k: t[k]); return t[i:] + t[:i]
def tris_list(b, n, vs): V = [b[i * vs:(i + 1) * vs] for i in range(n)]; return Counter(norm(tuple(V[i:i + 3])) for i in range(0, n, 3) if len(set(V[i:i + 3])) == 3)   # вырожденные (две вершины одинаковы) ничего не рисуют
def tris_strip(b, nv, ns, vs):
    V = [b[i * vs:(i + 1) * vs] for i in range(nv)]; lens = struct.unpack_from(f'<{ns}H', b, nv * vs); o = 0; c = Counter()
    for m in lens:
        for k in range(m - 2):
            t = (V[o + k], V[o + k + 1], V[o + k + 2]) if k % 2 == 0 else (V[o + k + 1], V[o + k], V[o + k + 2])
            if len(set(t)) == 3: c[norm(t)] += 1
        o += m
    return c
def main():
    a, b = sys.argv[1], sys.argv[2]; red = '--red' in sys.argv
    da, Ra, Ca = load(a); db, Rb, Cb = load(b); bad = 0; ns = 0; same = 0
    if len(Ra) != len(Rb) or len(Ca) != len(Cb): print('число кусков/клеток разное'); return 1
    if red:   # красный контроль: портим байт вершины первого куска-полосы в копии файла
        db = bytearray(db)
        for r in Rb:
            if r[7] & F_STRIP: db[Cb[r[17]][9] + r[15] + 16 + 8] ^= 0x55; break
        db = bytes(db)
    for j in range(len(Ra)):
        ra, rb = Ra[j], Rb[j]; sa = list(ra); sb = list(rb); sa[15] = sb[15] = 0; sa[7] |= F_STRIP; sb[7] |= F_STRIP
        if sa != sb: bad += 1; print('кусок', j, 'запись изменилась'); continue
        if ra[10] != 0: continue
        vs = 12 if ra[7] & 32 else 16; ba = da[Ca[ra[17]][9] + ra[15]:]; bb = db[Cb[rb[17]][9] + rb[15]:]; nv, ni, nf = ra[8], ra[9], ra[16]
        if rb[7] & F_STRIP:
            ns += 1; h = struct.unpack_from('<4I', bb, 0); p = 16
            sn = tris_strip(bb[p:], h[0], h[1], vs); p += h[0] * vs + ((h[1] * 2 + 3) & ~3)
            sf = tris_strip(bb[p:], h[2], h[3], vs) if h[2] else Counter()
            la = tris_list(ba, ni, vs); lf = tris_list(ba[ni * vs:], nf, vs) if nf else Counter()
            if sn != la or sf != lf: bad += 1; print('кусок', j, 'треугольники разошлись', sum(sn.values()), sum(la.values()))
        else:
            n = nv * vs if ra[7] & 16 else 0
            if n and ba[:n] != bb[:n]: bad += 1; print('кусок', j, 'не-полоса отличается')
            else: same += 1
    print(f'кусков {len(Ra)}: в полосах {ns}, без изменений {same}, расхождений {bad}')
    return 1 if bad else 0
sys.exit(main())
