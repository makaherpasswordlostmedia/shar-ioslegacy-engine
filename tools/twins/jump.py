#!/usr/bin/env python3
"""Близнецы · В22: прыжок в оригинале с разгона, как у игрока. Бот: по дорогам оригинала до точки разгона (зоны грузятся по ходу),
потом по прямой к точке старта прыжка курсом --heading с газом до --kmh, дальше 4 с полёта и посадки: трасса каждые 2 кадра, кадры экрана.

  python3 tools/twins/jump.py --start X Y Z --heading ГРАД --kmh 100 [--runup 120] [--lat 0] --out ID
Курс — atan2(нос.x, нос.z) в осях игры (0° = +z). Выход build/twins/o4/<ID>/: jump.tsv (кадр, x, y, z, курс, скорость, фаза), png/."""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D
import route as R


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--start', type=float, nargs=3, required=True); ap.add_argument('--heading', type=float, required=True)
    ap.add_argument('--kmh', type=float, default=100); ap.add_argument('--runup', type=float, default=120); ap.add_argument('--lat', type=float, default=0.0)
    ap.add_argument('--out', required=True); ap.add_argument('--after', type=int, default=200)
    ap.add_argument('--nosteer', type=float, default=0.0, help='последние N м разгона стик по центру (В28: рыскание без руля бота)')
    ap.add_argument('--place', type=float, nargs=6, default=None, help='после разгона: car_cm x y z и car_vel vx vy vz (адреса «можно»)'); a = ap.parse_args()
    hd = math.radians(a.heading); fx, fz = math.sin(hd), math.cos(hd); rx, rz = math.cos(hd), -math.sin(hd)   # вправо от курса
    sx, sz = a.start[0] + rx * a.lat, a.start[2] + rz * a.lat
    stage = (sx - fx * a.runup, sz - fz * a.runup)
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), ('разгон', stage[0], 4.0, stage[1])])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(stage[0], 4.0, stage[1])]
    pts, _ = R.resample(pts, 3.0)
    o = D.Original(C.OUT / 'o4' / a.out); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'jump.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\tфаза\n')
    phase, i, stuck, rev, last, t0 = 'дорога', 0, 0, 0, 0, 0; vt = a.kmh / 3.6
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, y, z = s['x'], s['y'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz']); cmds = []
        if phase == 'дорога':
            best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
            if best > i: i = best; last = f
            j = min(len(pts) - 1, i + 3); err = D.ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
            if rev > 0:
                rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
                if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
            else:
                st = max(-1.0, min(1.0, err * 2.5)); vv = 14.0 * max(0.35, math.cos(err))
                cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vv else 0}', f'pad circle {1 if v > vv + 5 else 0}']
                stuck = stuck + 2 if v < 0.8 else 0
                if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
            near_end = math.hypot(stage[0] - x, stage[1] - z) < 20 and stuck >= 40   # бездорожье у точки разгона: начать отсюда
            if math.hypot(stage[0] - x, stage[1] - z) < 6 or i >= len(pts) - 2 or near_end: phase, t0 = 'разгон', f
        elif phase == 'разгон':   # по прямой на старт: целимся в точку на 15 м впереди проекции на ось прыжка
            along = (x - stage[0]) * fx + (z - stage[1]) * fz
            tx, tz = stage[0] + fx * (along + 15), stage[1] + fz * (along + 15)
            err = D.ang(math.atan2(tx - x, tz - z) - h); st = max(-1.0, min(1.0, err * 2.0))
            if a.nosteer > 0 and along >= a.runup - 2 - a.nosteer: st = 0.0   # В28: без руля перед трамплином
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', 'pad circle 0']
            if along >= a.runup - 2: phase, t0 = 'полёт', f
            if f - t0 > 1500: phase, t0 = 'полёт', f
        elif phase == 'полёт':
            cmds = [*D.axis('l', 'x', 0.0), 'pad cross 1' if f - t0 < 20 else 'pad cross 0']
            if a.place and f - t0 < 4:   # хирургия ОРАКУЛ О3: тело машины и скорость (один телепорт с толчком), машина уже едет этим курсом
                cx, cy, cz, vx, vy, vz = a.place
                cmds += [f'f32 1298884 {cx}', f'f32 1298888 {cy}', f'f32 129888c {cz}', f'f32 a218b0 {vx}', f'f32 a218b4 {vy}', f'f32 a218b8 {vz}']
            if f - t0 > a.after: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        if phase != 'дорога' and f % 4 == 0 or f % 400 == 0: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f'{f}\t{x:.2f}\t{y:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{phase}\n')
        if f > 20000: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close(); print(f'фаза {phase}, кадр {o.frame} → {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
