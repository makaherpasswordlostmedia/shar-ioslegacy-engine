#!/usr/bin/env python3
"""Близнецы · правка Роба 200 (03.10): «через арку с гаечным ключом (навес голубого дома, ключ R1W1) к стеклу (glass180) —
медленно кусты не пропускают, выталкивают в разные стороны». Оригинал: со старта L1 по дорогам до въезда к навесу (оси оригинала
z = −z порта), дальше прямо на запад через навес к стеклу со скоростью не выше --vt; трасса каждые 2 кадра (x, z, курс,
скорость, боковая скорость), кадры экрана каждые --png кадров на подходе.
  python3 tools/twins/arch.py [--vt 3] [--png 10] [--after 900] --out v200_arch"""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D
import route as R

ENTRY = (180.0, -160.0)                                   # перед навесом, оси оригинала
LINE = [(170.0, -160.0), (157.0, -160.0), (140.0, -159.0), (127.4, -158.1), (115.0, -157.5)]   # навес → стекло glass180 → за ним


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--vt', type=float, default=3.0); ap.add_argument('--png', type=int, default=10)
    ap.add_argument('--after', type=int, default=900); ap.add_argument('--out', default='v200_arch'); a = ap.parse_args()
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), ('навес', ENTRY[0], 4.0, ENTRY[1])])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(ENTRY[0], 4.0, ENTRY[1])]
    pts, _ = R.resample(pts, 3.0)
    o = D.Original(C.OUT / 'o4' / a.out); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'arch.tsv').open('w'); tsv.write('кадр\tфаза\tx\ty\tz\tкурс\tv\tбок\n')
    phase, i, wi, t0, stuck, rev, last = 'дорога', 0, 0, 0, 0, 0, 0
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        lat = s['vx'] * s['nz'] - s['vz'] * s['nx']                      # боковая скорость (вправо от курса, оси оригинала)
        cmds = []
        if phase == 'дорога':
            best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
            if best > i: i = best; last = f
            j = min(len(pts) - 1, i + 3); err = D.ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
            if rev > 0:
                rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
                if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
            else:
                st = max(-1.0, min(1.0, err * 2.5)); vt = 10.0 * max(0.35, math.cos(err))
                cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 5 else 0}']
                stuck = stuck + 2 if v < 0.8 else 0
                if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
            if i >= len(pts) - 2: phase, t0 = 'к стеклу', f
        elif phase == 'к стеклу':
            tg = LINE[wi]
            if math.hypot(tg[0] - x, tg[1] - z) < 2.5 and wi < len(LINE) - 1: wi += 1; tg = LINE[wi]
            err = D.ang(math.atan2(tg[0] - x, tg[1] - z) - h); st = max(-1.0, min(1.0, err * 2.0))
            vf = s['vx'] * s['nx'] + s['vz'] * s['nz']
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < a.vt else 0}', f"pad circle {1 if vf > a.vt + 2.5 else 0}"]
            if f % a.png == 0: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
            if f - t0 > a.after: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        tsv.write(f"{f}\t{phase}\t{x:.2f}\t{s['y']:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{lat:.2f}\n")
        if f > 6000: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    print(f'→ {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
