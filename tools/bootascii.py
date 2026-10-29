#!/usr/bin/env python3
"""Логотип Роба (SVG) -> ASCII-арт строками символов для загрузочного экрана: viewer/bootascii.h.
tools/bootascii.py LOGO.svg [--cols 58]. Растр высокого разрешения -> доля заливки в каждой клетке символа -> " .:-=+*%#@".
Клетка квадратная: шрифт PSP 8×8."""
import argparse, re, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('svg'); ap.add_argument('--cols', type=int, default=58); ap.add_argument('--out', default='viewer/bootascii.h')
a = ap.parse_args()
src = open(a.svg).read()
vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
edges = []
for d in re.findall(r'\sd="([^"]+)"', src):
    toks = re.findall(r'[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?', d); st = {'i': 0}; x = y = sx = sy = 0.0; pts = []; cmd = None
    def num():
        v = float(toks[st['i']]); st['i'] += 1; return v
    def close(p):
        for k in range(len(p)): edges.append((p[k], p[(k + 1) % len(p)]))
    while st['i'] < len(toks):
        t = toks[st['i']]
        if t.isalpha(): cmd = t; st['i'] += 1
        if cmd in 'Zz': close(pts); pts = []; x, y = sx, sy; continue
        rel = cmd.islower(); c = cmd.upper()
        if c == 'M':
            if pts: close(pts)
            nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny); sx, sy = x, y; pts = [(x, y)]; cmd = 'l' if rel else 'L'; continue
        if c == 'H': v = num(); x = x + v if rel else v
        elif c == 'V': v = num(); y = y + v if rel else v
        elif c == 'L': nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny)
        elif c == 'S': num(); num(); nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny)
        pts.append((x, y))
    if pts: close(pts)
W = 1160; H = int(round(W * vb[3] / vb[2]))
X, Y = np.meshgrid(vb[0] + (np.arange(W) + .5) * vb[2] / W, vb[1] + (np.arange(H) + .5) * vb[3] / H)
ins = np.zeros(X.shape, bool)
for (x0, y0), (x1, y1) in edges:
    if y0 == y1: continue
    m = (Y >= min(y0, y1)) & (Y < max(y0, y1)); xi = x0 + (Y - y0) * (x1 - x0) / (y1 - y0); ins ^= m & (X < xi)
ys, xs = np.where(ins); ins = ins[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
cw = ins.shape[1] / a.cols; rows_n = int(round(ins.shape[0] / cw)); ch = ins.shape[0] / rows_n
ramp = " .:-=+*%#@"
rows = []
for r in range(rows_n):
    line = ''.join(ramp[min(len(ramp) - 1, int(ins[int(r * ch):int((r + 1) * ch), int(c * cw):int((c + 1) * cw)].mean() * (len(ramp) - 1) + .5))] for c in range(a.cols))
    rows.append(line.rstrip())
body = ''.join('  "' + l.replace('\\', '\\\\') + '",\n' for l in rows)
open(a.out, 'w').write('// Логотип GONE Makers Co. в ASCII (строки символов) — сгенерировано tools/bootascii.py из SVG Роба\n'
                       '#define BOOTASCII_H ' + str(len(rows)) + '\nstatic const char *const bootAscii[BOOTASCII_H] = {\n' + body + '};\n')
print(a.cols, 'x', len(rows)); print('\n'.join(rows))
