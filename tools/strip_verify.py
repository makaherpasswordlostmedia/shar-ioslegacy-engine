#!/usr/bin/env python3
"""Проверка stripbench.bin (tools/strip_probe --emit): список, отдельные полосы и одна полоса с вырожденными дают одно и то же множество
треугольников с тем же обходом (вершины сравниваются побайтно). python3 -I tools/strip_verify.py stripbench.bin"""
import struct, sys
from collections import Counter
d = open(sys.argv[1], 'rb').read(); assert d[:4] == b'SBN1'; n = struct.unpack_from('<I', d, 4)[0]; p = 8; bad = 0; tl = ts = tw = 0
def norm(t):   # поворот так, чтобы наименьшая вершина первой (обход сохраняется)
    i = min(range(3), key=lambda k: t[k]); return t[i:] + t[:i]
for _ in range(n):
    h = struct.unpack_from('<IIiIffffIIII6f', d, p); p += 72
    pi, fl, tex, vs = h[:4]; nl, nsv, nst, nsw = h[8:12]
    L = [d[p + i * vs:p + (i + 1) * vs] for i in range(nl)]; p += nl * vs
    S = [d[p + i * vs:p + (i + 1) * vs] for i in range(nsv)]; p += nsv * vs
    ln = struct.unpack_from(f'<{nst}H', d, p); p += (nst * 2 + 3) // 4 * 4
    W = [d[p + i * vs:p + (i + 1) * vs] for i in range(nsw)]; p += nsw * vs; p = (p + 15) & ~15
    a = Counter(norm(tuple(L[i:i + 3])) for i in range(0, nl, 3))
    b = Counter(); o = 0
    for m in ln:
        for k in range(m - 2):
            t = (S[o + k], S[o + k + 1], S[o + k + 2]) if k % 2 == 0 else (S[o + k + 1], S[o + k], S[o + k + 2]); (b.update([norm(t)]) if len(set(t)) == 3 else None)
        o += m
    assert o == nsv
    c = Counter()
    for k in range(nsw - 2):
        t = (W[k], W[k + 1], W[k + 2]) if k % 2 == 0 else (W[k + 1], W[k], W[k + 2])
        if len(set(t)) == 3: c[norm(t)] += 1
    # одинаковые по байтам вершины в разных треугольниках сливаются корректно: сравниваем множества и счётчики
    if a != b or a != c: bad += 1; print('кусок', pi, 'разошёлся: список', sum(a.values()), 'полосы', sum(b.values()), 'сшитая', sum(c.values()))
    tl += nl; ts += nsv; tw += nsw
print(f'кусков {n}, расхождений {bad}; вершин: список {tl}, полосы {ts}, сшитая {tw}')
