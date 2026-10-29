"""Карта всего уровня с точками событий cartest (отменённые подшаги по причинам) и стартами.
python tools/cartest/events_png.py LEVEL.shr DIR [--px 1]  -> DIR/events.png
Причины: 1 не вытолкнулось — красный, 16 край мира — пурпурный, 2/4/8 заборы — жёлтый."""
import sys, csv, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from col_check import load, parse_col

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('dir'); ap.add_argument('--px', type=float, default=1.0)
    a = ap.parse_args(); b, L = load(a.level); C = parse_col(b, L['col']); s = a.px
    x0, z0 = C['ox'], C['oz']; W, H = int(C['W'] * C['cell'] * s), int(C['H'] * C['cell'] * s)
    img = Image.new('RGB', (W, H), (15, 15, 18)); d = ImageDraw.Draw(img); P = lambda x, z: ((x - x0) * s, (z - z0) * s)
    T = C['tri']; ys = T[:, :3, 1].mean(1); lo, hi = np.percentile(ys, 2), np.percentile(ys, 98)
    for t, y in zip(T, ys):
        g = int(40 + 120 * np.clip((y - lo) / (hi - lo), 0, 1)); d.polygon([P(t[k, 0], t[k, 2]) for k in range(3)], fill=(g, g, g) if t[3, 1] > .5 else (150, 40, 40))
    for bx in C['box']:
        c = bx[:3]; A = bx[3:12].reshape(3, 3); h = bx[12:15]; e = np.abs(A[:, [0, 2]]).T @ h
        d.rectangle([P(c[0] - e[0], c[2] - e[1]), P(c[0] + e[0], c[2] + e[1])], outline=(70, 120, 230))
    for g in C['seg']: d.line([P(g[0], g[1]), P(g[2], g[3])], fill=(230, 200, 40), width=1)
    col = {1: (255, 40, 40), 16: (255, 0, 255)}
    f = Path(a.dir) / 'reverts.csv'
    if f.exists():
        for r in csv.DictReader(open(f)):
            x, z, w = float(r['x']), float(r['z']), int(r['why']); u, v = P(x, z)
            d.rectangle([u - 1, v - 1, u + 1, v + 1], fill=col.get(w, (255, 255, 0)))
    img.save(Path(a.dir) / 'events.png'); print(Path(a.dir) / 'events.png')

if __name__ == '__main__': main()
