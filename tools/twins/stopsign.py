#!/usr/bin/env python3
"""Близнецы · правка Роба 226 (03.10: «знаки STOP задом наперёд, везде»): оригинал со старта L1 едет по дорогам к знаку
l1_stopsign (l1r1, оригинал (102,48; 3,49; −164,76)) и снимает кадры экрана — как знак выглядит у PS2 с дороги.
  python3 tools/twins/stopsign.py [--to X Z] [--png 6] --out v226_stop
Сверка с портом: тот же знак в порту (z порта = −z оригинала) — сценарий build/twins/scen stop2 (камера с четырёх сторон)."""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D
import route as R


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--to', type=float, nargs=2, default=(118.0, -165.0))
    ap.add_argument('--png', type=int, default=6); ap.add_argument('--out', default='v226_stop'); ap.add_argument('--frames', type=int, default=2400)
    a = ap.parse_args()
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), ('знак', a.to[0], 3.5, a.to[1])])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(a.to[0], 3.5, a.to[1])]
    pts, _ = R.resample(pts, 3.0)
    o = D.Original(C.OUT / 'o4' / a.out); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'stop.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\n')
    i, last, stuck, rev, done = 0, 0, 0, 0, None
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
        if best > i: i = best; last = f
        j = min(len(pts) - 1, i + 3); err = D.ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
        dist = math.hypot(a.to[0] - x, a.to[1] - z)
        if done is None and (dist < 5 or i >= len(pts) - 2): done = f
        if done is not None:
            cmds = [*D.axis('l', 'x', 0.0), 'pad cross 0', f'pad circle {1 if v > .5 else 0}']
        elif rev > 0:
            rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
            if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
        else:
            st = max(-1.0, min(1.0, err * 2.5)); vv = 9.0 * max(0.35, math.cos(err))
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vv else 0}', f'pad circle {1 if v > vv + 5 else 0}']
            stuck = stuck + 2 if v < 0.8 else 0
            if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
        if f % a.png == 0 and f >= 40 and dist < 60: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f"{f}\t{x:.2f}\t{s['y']:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\n")
        if f >= a.frames or (done is not None and f - done > 60): o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    print(f'→ {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
