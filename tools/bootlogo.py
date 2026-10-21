#!/usr/bin/env python3
"""Логотип Роба (пиксельный SVG на сетке 3.55) -> ASCII-битмап для загрузочного экрана (viewer/bootlogo.h).
tools/bootlogo.py LOGO.svg [--out viewer/bootlogo.h]. Контуры из прямых (M/L/H/V/Z, вырожденные s/S), чётно-нечётная заливка."""
import argparse, re, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('svg'); ap.add_argument('--out', default='viewer/bootlogo.h'); ap.add_argument('--cell', type=float, default=3.55)
a = ap.parse_args()
src = open(a.svg).read()
vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
color = re.search(r'fill:\s*#([0-9a-fA-F]{6})', src); color = color.group(1) if color else 'fcb3a0'
edges = []
for d in re.findall(r'\sd="([^"]+)"', src):
    toks = re.findall(r'[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?', d)
    i, cmd, x, y, sx, sy = 0, None, 0.0, 0.0, 0.0, 0.0
    def num():
        global i
        v = float(toks[i]); i += 1; return v
    pts = []
    def close():
        global pts
        for k in range(len(pts)): edges.append((pts[k], pts[(k + 1) % len(pts)]))
        pts = []
    while i < len(toks):
        t = toks[i]
        if t.isalpha(): cmd = t; i += 1
        if cmd in 'Zz':
            close(); x, y = sx, sy; continue
        rel = cmd.islower(); c = cmd.upper()
        if c == 'M':
            if pts: close()
            nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny); sx, sy = x, y; pts = [(x, y)]; cmd = 'l' if rel else 'L'; continue
        if c == 'H': v = num(); x = x + v if rel else v
        elif c == 'V': v = num(); y = y + v if rel else v
        elif c == 'L': nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny)
        elif c == 'S': num(); num(); nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny)
        elif c == 'C': [num() for _ in range(4)]; nx, ny = num(), num(); x, y = (x + nx, y + ny) if rel else (nx, ny)
        else: raise SystemExit('команда не поддержана: ' + cmd)
        pts.append((x, y))
    if pts: close()
E = np.array(edges)                                    # (n, 2, 2)
W, H = int(round(vb[2] / a.cell)), int(round(vb[3] / a.cell))
cx = vb[0] + (np.arange(W) + .5) * vb[2] / W; cy = vb[1] + (np.arange(H) + .5) * vb[3] / H
X, Y = np.meshgrid(cx, cy)
(x0, y0), (x1, y1) = E[:, 0].T, E[:, 1].T
inside = np.zeros(X.shape, bool)
for ex0, ey0, ex1, ey1 in zip(x0, y0, x1, y1):   # луч вправо: чётно-нечётное правило
    if ey0 == ey1: continue
    m = (Y >= min(ey0, ey1)) & (Y < max(ey0, ey1))
    xi = ex0 + (Y - ey0) * (ex1 - ex0) / (ey1 - ey0)
    inside ^= m & (X < xi)
rows = [''.join('#' if v else ' ' for v in r).rstrip() for r in inside]
while rows and not rows[0].strip(): rows.pop(0)
while rows and not rows[-1].strip(): rows.pop()
lead = min(len(r) - len(r.lstrip()) for r in rows if r.strip()); rows = [r[lead:] for r in rows]
w = max(len(r) for r in rows)
with open(a.out, 'w') as f:
    f.write('// Логотип GONE Makers Co. для загрузочного экрана — сгенерировано tools/bootlogo.py из SVG Роба, не править руками\n')
    f.write(f'#define BOOTLOGO_W {w}\n#define BOOTLOGO_H {len(rows)}\n#define BOOTLOGO_RGB 0x{color[4:6]}{color[2:4]}{color[0:2]}   // ABGR без альфы: #{color}\n')
    f.write('static const char *const bootLogo[BOOTLOGO_H] = {\n' + ''.join(f'  "{r}",\n' for r in rows) + '};\n')
print(f'{w}x{len(rows)}'); print('\n'.join(rows))
