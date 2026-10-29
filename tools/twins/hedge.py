#!/usr/bin/env python3
"""Близнецы · правка Роба 200 (03.10): «со старта ехать прямо по ходу машины, через арку с гаечным ключом — кусты медленно не
пропускают, а выталкивают в стороны». Оригинал со старта L1 (в машине у дома): руль по центру, газ импульсами до --vt м/с,
--frames кадров прямо; трасса каждые 2 кадра (x, z, курс, скорость), кадры экрана каждые --png кадров.
  python3 tools/twins/hedge.py [--vt 4] [--frames 700] [--png 10] --out v200_hedge
Сверка с портом: тот же старт и газ — tests/airwalls/host.sh drop 215.05 4.6 170.25 -163 0 0 SECS (AW_GAS)."""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--vt', type=float, default=4.0); ap.add_argument('--frames', type=int, default=700)
    ap.add_argument('--png', type=int, default=10); ap.add_argument('--out', default='v200_hedge'); a = ap.parse_args()
    o = D.Original(C.OUT / 'o4' / a.out); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'hedge.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\tгаз\n')
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        gas = 40 <= f and v < a.vt
        cmds = [*D.axis('l', 'x', 0.0), f'pad cross {1 if gas else 0}', 'pad circle 0']
        if f % a.png == 0 and f >= 40: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f"{f}\t{s['x']:.2f}\t{s['y']:.2f}\t{s['z']:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{int(gas)}\n")
        if f >= a.frames: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    print(f'→ {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
