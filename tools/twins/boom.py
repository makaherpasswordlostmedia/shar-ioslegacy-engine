#!/usr/bin/env python3
"""Близнецы · правка Роба 199 (03.10): «недоработана анимация, что они взрываются». Оригинал: машина Гомера со старта L1 таранит
изгородь через улицу (твёрдая, близнец hedge.py) — разгон, удар, задний ход, снова — пока не взорвётся; трасса каждые 2 кадра
(x, y, z, курс, скорость, вертикальная скорость), кадры экрана каждые --png кадров начиная с удара --from.
  python3 tools/twins/boom.py [--frames 7000] [--png 4] [--from 4] --out v199_boom"""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--frames', type=int, default=7000); ap.add_argument('--png', type=int, default=4)
    ap.add_argument('--from', dest='from_', type=int, default=4); ap.add_argument('--out', default='v199_boom'); a = ap.parse_args()
    o = D.Original(C.OUT / 'o4' / a.out, extra=[('vy', 0xa218b4, 'f32')]); (o.out / 'png').mkdir(exist_ok=True)   # car_vel[1]
    tsv = (o.out / 'boom.tsv').open('w'); tsv.write('кадр\tфаза\tудар\tx\ty\tz\tкурс\tv\tvy\n')
    phase, t0, hits, vmax, h0 = 'разгон', 0, 0, 0.0, None
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz']); h0 = h if h0 is None else h0
        cmds = [*D.axis('l', 'x', 0.0)]
        if f < 40: cmds += ['pad cross 0', 'pad circle 0']
        elif phase == 'разгон':
            cmds += ['pad cross 1', 'pad circle 0']; vmax = max(vmax, v)
            if vmax > 6 and v < 0.6 * vmax and f - t0 > 30: hits += 1; phase, t0, vmax = 'удар', f, 0.0
            elif f - t0 > 400: phase, t0 = 'назад', f
        elif phase == 'удар':
            cmds += ['pad cross 0', 'pad circle 0']
            if f - t0 > 40: phase, t0 = 'назад', f
        elif phase == 'назад':                                    # задний ход «кружком» ~2,2 с (метров 25)
            err = D.ang(h0 - h); cmds = [*D.axis('l', 'x', max(-1.0, min(1.0, -err * 2.0))), 'pad cross 0', 'pad circle 1']
            if f - t0 > 130: phase, t0 = 'стоп', f
        elif phase == 'стоп':
            cmds += ['pad cross 0', 'pad circle 0']
            if f - t0 > 20: phase, t0, vmax = 'разгон', f, 0.0
        if hits >= a.from_ and f % a.png == 0: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f"{f}\t{phase}\t{hits}\t{s['x']:.2f}\t{s['y']:.2f}\t{s['z']:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{s.get('vy', 0.0):.2f}\n")
        if f >= a.frames: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    print(f'→ {o.out.relative_to(C.DATA)}, ударов {hits}')


if __name__ == '__main__':
    main()
