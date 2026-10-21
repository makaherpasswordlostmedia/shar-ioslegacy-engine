#!/usr/bin/env python3
"""Правка 416: по снимкам tests/far416/gen.sh — мерцание дали и щели.
n = тот же кадр без сдвига (пол шума). shimmer = среднее |a−b| (RGB, 0..441) по пикселям маски m (город дальше 60 м) при сдвиге машины на 4 см; flick = доля пикселей маски
с |a−b| > 48; detail = средний перепад яркости соседних пикселей по маске (сколько деталей осталось вдали); crack = пурпур кадра k (clearchk+nosky) внутри маски m в тонких полосах (≤ 2 px по горизонтали или вертикали) на 10 000 px маски.
measure.py DIR [--json OUT]"""
import sys, glob, json, os, numpy as np
from PIL import Image
def L(p): return np.asarray(Image.open(p).convert('RGB')).astype(float)
def key(M): return (M[..., 0] > 200) & (M[..., 1] < 70) & (M[..., 2] > 200)
def thin(m, n=2):
    out = np.zeros_like(m)
    for ax in (0, 1):
        a = m if ax == 1 else m.T
        o = np.zeros_like(a)
        for y in range(a.shape[0]):
            r = a[y]; x = 0
            while x < len(r):
                if r[x]:
                    e = x
                    while e < len(r) and r[e]: e += 1
                    if e - x <= n and x > 0 and e < len(r): o[y, x:e] = True
                    x = e
                else: x += 1
        out |= o if ax == 1 else o.T
    return out
d = sys.argv[1]; res = {}
for n in range(1, 8):
    px = 0; sd = 0.0; fl = 0; cr = 0; sn = 0.0; fn = 0; dt = 0.0; frames = 0
    for a in sorted(glob.glob(f'{d}/L{n}h*_a.png')):
        b = a[:-6]
        if not all(os.path.exists(f'{b}_{k}.png') for k in 'bmkn'):
            print(f'Incomplete frame set: {b}', file=sys.stderr); sys.exit(2)
        A, B, M, K = L(a), L(b + '_b.png'), key(L(b + '_m.png')), key(L(b + '_k.png'))
        M[200:, 380:] = False
        frames += 1
        if not M.sum(): continue
        dd = np.linalg.norm(A[M] - B[M], axis=1)
        dn = np.linalg.norm(A[M] - L(b + '_n.png')[M], axis=1); sn += dn.sum(); fn += int((dn > 48).sum())
        g = A.mean(2); gx = np.zeros_like(g); gy = np.zeros_like(g); gx[:, 1:] = np.abs(np.diff(g, axis=1)); gy[1:] = np.abs(np.diff(g, axis=0)); dt += (gx + gy)[M].sum()
        px += int(M.sum()); sd += dd.sum(); fl += int((dd > 48).sum()); cr += int((thin(K) & M).sum())
    if frames != 4 or not px:
        print(f'L{n}: coverage {frames}/4, pixels {px}', file=sys.stderr); sys.exit(2)
    res[f'L{n}'] = {'frames': frames, 'px': px, 'shimmer': round(float(sd) / px, 2), 'flick%': round(100 * fl / px, 2), 'crack_per10k': round(1e4 * cr / px, 2), 'noise': round(float(sn) / px, 2), 'noise_flick%': round(100 * fn / px, 2), 'detail': round(float(dt) / px, 2)}
    print(f'L{n}', res[f'L{n}'])
if len(sys.argv) > 3 and sys.argv[2] == '--json': json.dump(res, open(sys.argv[3], 'w'), indent=1)
