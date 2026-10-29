#!/usr/bin/env python3
# №928: поиск крупных высоких объектов уровня (кандидаты в ориентиры дали: маяк, обсерватория, трубы, башни, колесо, церковь). По геометрии level.shr (без прозрачного и неба): карта максимальной высоты на сетке STEP м;
# локальные пики с превышением над окрестностью (медиана высот в кольце 40..120 м вокруг) ≥ PROM м и малой площадью (≤ AREA м в поперечнике); соседние пики одного объекта сливаются. Для точки наблюдателя (--eye x,z,y) — расстояние и угол места.
# landmark_scan.py level.shr [--prom 25] [--eye x,z,y] [--json out.json]
import sys, json, argparse, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import shr7read
ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('--prom', type=float, default=25.); ap.add_argument('--step', type=float, default=8.); ap.add_argument('--eye'); ap.add_argument('--json'); ap.add_argument('--top', type=int, default=24); a = ap.parse_args()
d = shr7read.load(a.level, far=False, owner=0); keep = (d['FL'] & (1 | 2 | 4)) == 0; V = d['P'][keep].reshape(-1, 3)
V = np.concatenate([V, d['P'][keep].mean(1)]); st = a.step
x0, z0 = np.floor(V[:, 0].min() / st) * st, np.floor(V[:, 2].min() / st) * st
gx = ((V[:, 0] - x0) / st).astype(int); gz = ((V[:, 2] - z0) / st).astype(int); W, H = gx.max() + 1, gz.max() + 1
top = np.full((H, W), -1e9, np.float32); np.maximum.at(top, (gz, gx), V[:, 1]); low = np.full((H, W), 1e9, np.float32); np.minimum.at(low, (gz, gx), V[:, 1])
occ = top > -1e8
r1, r2 = int(40 / st), int(120 / st); peaks = []
base_ = np.where(occ, top, -1e9); loc = base_.copy(); k = int(24 / st)   # максимум в окне ±24 м без scipy
for dj in range(-k, k + 1):
    for di in range(-k, k + 1):
        sh = np.full_like(base_, -1e9); sh[max(0, dj):H + min(0, dj), max(0, di):W + min(0, di)] = base_[max(0, -dj):H + min(0, -dj), max(0, -di):W + min(0, -di)]; loc = np.maximum(loc, sh)
cand = np.argwhere(occ & (top >= loc - 1e-3))
for (j, i) in cand:
    j0, j1, i0, i1 = max(0, j - r2), min(H, j + r2 + 1), max(0, i - r2), min(W, i + r2 + 1)
    sub = top[j0:j1, i0:i1]; yy, xx = np.mgrid[j0:j1, i0:i1]; rr = np.hypot(yy - j, xx - i) * st
    ring = sub[(rr >= 40) & (rr <= 120) & (sub > -1e8)]
    if len(ring) < 20: continue
    base = float(np.median(ring)); pr = float(top[j, i]) - base
    if pr >= a.prom: peaks.append((pr, x0 + (i + .5) * st, z0 + (j + .5) * st, float(top[j, i]), base))
peaks.sort(reverse=True); sel = []
for p in peaks:   # слияние соседних (< 40 м) пиков
    if all(np.hypot(p[1] - q[1], p[2] - q[2]) > 40 for q in sel): sel.append(p)
ex = [float(v) for v in a.eye.split(',')] if a.eye else None
out = []
for pr, x, z, y, b in sel[:a.top]:
    # радиус объекта: связная область вокруг пика, где высота выше середины между основанием и вершиной (заливка по сетке), в пределах 8..45 м
    ci, cj = int((x - x0) / st), int((z - z0) / st); thr = b + .5 * (y - b); seen = {(cj, ci)}; fr = [(cj, ci)]; rmax = 0.
    while fr:
        jj, ii = fr.pop()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (jj + dj, ii + di)
            if q in seen or not (0 <= q[0] < H and 0 <= q[1] < W) or top[q] < thr or np.hypot((q[0] - cj) * st, (q[1] - ci) * st) > 45: continue
            seen.add(q); fr.append(q); rmax = max(rmax, float(np.hypot((q[0] - cj) * st, (q[1] - ci) * st)))
    row = {'x': round(x), 'z': round(z), 'top': round(y, 1), 'base': round(b, 1), 'prom': round(pr, 1), 'r': round(max(8., rmax + st), 0)}
    if ex: dd = float(np.hypot(x - ex[0], z - ex[1])); row['dist'] = round(dd); row['elev_deg'] = round(float(np.degrees(np.arctan2(y - ex[2], dd))), 1)
    out.append(row); print(row)
if a.json: json.dump(out, open(a.json, 'w'), ensure_ascii=False, indent=1)
