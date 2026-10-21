#!/usr/bin/env python3
"""Почему камера PS2 и порта расходятся: для групп расхождений — в каких триггерах Гомер (с объёмом), какая камера у PS2 (по глазу), какая у порта.
  python3 tests/rooms/roomcam_why.py ПАКЕТ.bin КОМНАТА ЗАПИСЬ.tsv [yстарт]"""
import math, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roomcam_twins as T
pkg, room, path = sys.argv[1], sys.argv[2], Path(sys.argv[3]); ys = float(sys.argv[4]) if len(sys.argv) > 4 else -20.0
dump = subprocess.run(['/tmp/trigdump', pkg, room], capture_output=True, text=True).stdout
cams = []
for l in dump.splitlines():
    if not l.startswith(' '):
        m = re.match(r'(\d+) (\S+) type(\d)', l); cams.append(dict(name=m[2][4:], type=int(m[3]), trig=[], pts=[], pos=None))
    elif 'trig' in l:
        v = [float(x) for x in re.findall(r'-?\d+\.\d+', l)]; cams[-1]['trig'].append(v)
    elif 'pos' in l: cams[-1]['pos'] = tuple(float(x) for x in re.findall(r'-?\d+\.\d+', l))
    elif 'pts' in l: cams[-1]['pts'] = [tuple(float(x) for x in p.split()) for p in re.findall(r'\(([^)]*)\)', l)]
def vol(t): return 8 * t[3] * t[4] * t[5]
def inside(c, x, z):
    best = None
    for t in c['trig']:
        # оси: ax0, ax2 даны (xz) — поворот по ax0
        a0 = (t[6], t[8]); dx, dz = x - t[0], z - t[2]; u = dx * a0[0] + dz * a0[1]; w = -dx * a0[1] + dz * a0[0]
        if abs(u) <= t[3] and abs(w) <= t[5]: best = vol(t) if best is None else min(best, vol(t))
    return best
def ident(e):
    best = (9e9, '?')
    for c in cams:
        if c['type'] == 0 and c['pos']: d = math.dist(c['pos'], e); best = min(best, (d, c['name']))
        elif c['type'] == 1:
            for a, b in zip(c['pts'], c['pts'][1:] or [c['pts'][0]]):
                ab = [b[k] - a[k] for k in range(3)]; ae = [e[k] - a[k] for k in range(3)]; L = sum(v * v for v in ab) or 1e-9
                t = max(0, min(1, sum(ae[k] * ab[k] for k in range(3)) / L)); q = [a[k] + ab[k] * t for k in range(3)]; best = min(best, (math.dist(q, e), c['name']))
    return best[1] if best[0] < 0.7 else '?'
orig = T.original(path, ('trace', ys)); host = T.build(0); tsv = T.ROOT / 'build/rooms_cams/path_why.tsv'
tsv.write_text(''.join(f'{f} {x:.3f} {z:.3f}\n' for f, x, z, _, _ in orig))
res = subprocess.run([str(host), pkg, room, str(tsv)], capture_output=True, text=True, check=True).stdout
port = {int(l.split('\t')[0]): l.split('\t') for l in res.splitlines()}
rows = []
for i, (f, x, z, e, d) in enumerate(orig):
    p = port.get(f)
    if not p: continue
    pe = [float(v) for v in p[2:5]]; rows.append((f, x, z, ident(e), p[1][4:], math.dist(e, pe) > T.EYE_TOL))
last = None
for f, x, z, ps, pt, bad in rows:
    key = (ps, pt, bad)
    if key != last:
        ins = ' '.join(f'{c["name"]}={inside(c, x, z):.0f}' for c in cams if inside(c, x, z) is not None)
        print(f'{f}: Гомер ({x:.2f},{z:.2f}) PS2={ps} порт={pt} {"РАСХОЖДЕНИЕ" if bad else "ок"}  в триггерах: {ins}')
    last = key
