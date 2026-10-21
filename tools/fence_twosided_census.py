#!/usr/bin/env python3
"""Двусторонние заборы порта: пары звеньев ColSeg с противоположными нормалями на одной линии (расстояние < 0,5 м, общий отрезок > 1 м). Забор оригинала односторонний (проба PS2 15.10,
звено 121 L1: держит со стороны нормали, с обратной машина проезжает), двойная линия у порта сделала бы его двусторонним. fence_twosided_census.py LEVEL.shr [...]"""
import sys, struct, numpy as np
for path in sys.argv[1:]:
    d = open(path, 'rb').read(); co, ce = struct.unpack_from('<II', d, 92); sec = d[co:]
    ntri, nbox, ncyl, nseg = struct.unpack_from('<4I', sec, 24)
    off = 48 + ntri * 48 + nbox * 64 + ncyl * 48
    S = np.frombuffer(sec, '<f4', nseg * 8, off).reshape(-1, 8).astype(np.float64)
    a, b, n = S[:, 0:2], S[:, 2:4], S[:, 4:6]; y0, y1 = S[:, 6], S[:, 7]
    keep = np.nonzero(y0 > -1.5e6)[0]; pairs = []
    mid = (a + b) / 2
    for ii, i in enumerate(keep):
        L = np.hypot(*(b[i] - a[i])); t = (b[i] - a[i]) / max(L, 1e-9)
        for j in keep[ii + 1:]:
            if np.dot(n[i], n[j]) > -0.9: continue
            if np.hypot(*(mid[i] - mid[j])) > (L + np.hypot(*(b[j] - a[j]))) / 2 + 1: continue
            dist = abs(np.dot(mid[j] - a[i], n[i]))
            if dist > 0.5: continue
            pj = [np.dot(a[j] - a[i], t), np.dot(b[j] - a[i], t)]; ov = min(L, max(pj)) - max(0, min(pj))
            if ov > 1.0: pairs.append((i, j, ov, dist))
    both = sum(p[2] for p in pairs)
    print(f"{path}: звеньев {nseg}, пар встречных нормалей на одной линии {len(pairs)} (общий отрезок {both:.0f} м)")
    for i, j, ov, dist in sorted(pairs, key=lambda p: -p[2])[:6]: print(f"   звенья {i} и {j}: общий отрезок {ov:.1f} м, расстояние {dist:.2f} м, середина ({mid[i][0]:.1f} {mid[i][1]:.1f}) верх {y1[i]:.1f}/{y1[j]:.1f}")
