#!/usr/bin/env python3
# №972: check.py img PNG | data A B
#   img: в рамке под кузовом дальней версии (колёса, днище) нет «цветных» пикселей (зелёнее красного на 30 и больше) и много тёмных; код возврата 0 — тёмный низ
#   data: в боковых файлах машин миссий (carflatm930.bin, L3) почти чёрных вершин у новых не меньше 1,3 раза больше, чем у старых
import struct, sys
import numpy as np
if sys.argv[1] == 'img':
    from PIL import Image
    a = np.asarray(Image.open(sys.argv[2]).convert('RGB'), int)[185:240, 120:260]; r, g, b = a[..., 0], a[..., 1], a[..., 2]
    col = int(((g > r + 30) & (g >= 60) & (g > b + 10)).sum()); dark = int((a.max(2) < 60).sum())
    print('  %s: цветных пикселей под кузовом %d, тёмных %d' % (sys.argv[2].split('/')[-2], col, dark)); sys.exit(0 if col <= 100 and dark >= 3000 else 1)
if sys.argv[1] == 'data':
    def dark(fn):
        b = open(fn, 'rb').read(); nm = struct.unpack_from('<I', b, 4)[0]; n = 0
        for m in range(nm):
            e = struct.unpack_from('<16sIIIII', b, 8 + 36 * m); cnt, off, ln = e[3], e[4], e[5]; p = off; end = off + ln
            for _ in range(cnt):
                if p + 12 > end: break
                pi, nt, K = struct.unpack_from('<III', b, p); c = np.frombuffer(b, np.uint8, 9 * K, p + 12).reshape(-1, 3); n += int((c.max(1) < 45).sum()); p += (12 + 9 * K + (2 * nt if K < nt else 0) + 3) & ~3
        return n
    a, b_ = dark(sys.argv[2]), dark(sys.argv[3]); print('  почти чёрных вершин у машин миссий L3: новые %d, старые %d, отношение %.2f' % (a, b_, a / max(b_, 1))); sys.exit(0 if a >= 1.3 * b_ else 1)
