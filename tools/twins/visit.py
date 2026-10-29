#!/usr/bin/env python3
"""Близнецы · О4: доехать по дорогам, выйти, дойти пешком, нажать и походить внутри — один прогон оригинала (lockstep).

  python3 tools/twins/visit.py --door KwikEMart [--seq "triangle@40,lup@200+90,…"] [--out v11_kwik]
Двери — build/interiors-l1.json (оси порта, z = −z оригинала); подход — 5,5 м перед дверью по её оси, потом в дверь.
Фазы: дорога (route.route_roads до точки у двери, бот drive) → тормоз («кружок») → выход («треугольник») → пешком (как walk.py) →
кнопки --seq от прихода, кадры экрана каждые --png кадров. Гомер — перенос матрицы 0xa24a40 (walk.py)."""
import argparse, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D
import route as R
import walk as W


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--door', required=True); ap.add_argument('--seq', default='triangle@40')
    ap.add_argument('--after', type=int, default=700); ap.add_argument('--png', type=int, default=10); ap.add_argument('--out', default=None)
    ap.add_argument('--vmax', type=float, default=14.0); ap.add_argument('--cam', action='store_true', help='писать позицию камеры (cam_pos) в cam.tsv')
    ap.add_argument('--inside', type=float, nargs=2, default=None, help='точка внутри (оси оригинала): дойти после входа'); ap.add_argument('--seq2', default='triangle@20')
    a = ap.parse_args()
    door = next(x for x in json.loads((C.DATA / 'build/interiors-l1.json').read_text())['doors'] if x['name'] == a.door)
    dx, dz = door['pos'][0], -door['pos'][2]
    front = (dx, dz + 5.5) if abs(door.get('heading', 0)) > 1.5 else (dx + 5.5, dz)   # дверь смотрит на +z оригинала (как у дома)
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), (a.door, front[0], 4.0, front[1] + 6)])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(front[0], 4.0, front[1] + 3)]
    pts, _ = R.resample(pts, 3.0)
    CAM = [('camx', 0x7aaba0, 'f32'), ('camy', 0x7aaba4, 'f32'), ('camz', 0x7aaba8, 'f32'),   # addrs.tsv cam_pos (наблюдение 01.10)
           ('camfx', 0x7aabb8, 'f32'), ('camfy', 0x7aabbc, 'f32'), ('camfz', 0x7aabc0, 'f32')]   # cam_fwd (правка 186, 03.10)
    o = D.Original(C.OUT / 'o4' / (a.out or f'visit_{a.door}'), extra=W.HOMER + (CAM if a.cam else [])); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'visit.tsv').open('w'); tsv.write('кадр\tфаза\tмашина x\tz\tv\tГомер x\tz\n')
    phase, t0, i = 'дорога', 0, 0; stuck = rev = 0; last = 0
    wps = [front, (dx, dz + 0.3)]; wi = 0; cam = cmd_ang = seg = None; hist = []; side_until = -1; side = 1; side_win = False
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        hx, hz = s['hx'], s['hz']; cmds = []
        if phase == 'дорога':
            best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
            if best > i: i = best; last = f
            j = min(len(pts) - 1, i + 3); err = D.ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
            if rev > 0:
                rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
                if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
            else:
                st = max(-1.0, min(1.0, err * 2.5)); vt = a.vmax * max(0.35, math.cos(err))
                cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 5 else 0}']
                stuck = stuck + 2 if v < 0.8 else 0
                if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
            if i >= len(pts) - 2: phase, t0 = 'тормоз', f; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', 0.0)]
        elif phase == 'тормоз':   # «кружок» — тормоз только пока катится вперёд; встала — отпустить (иначе задний ход)
            vf = s['vx'] * s['nx'] + s['vz'] * s['nz']
            cmds = ['pad cross 0', 'pad circle 1' if vf > 1.0 else 'pad circle 0']
            if vf <= 1.0 and v < 1.5 and f - t0 > 20: phase, t0 = 'выход', f; cmds = ['pad circle 0']
        elif phase == 'выход':
            cmds = ['pad triangle 1'] if f - t0 < 6 else ['pad triangle 0']
            if f - t0 >= 150: phase, t0 = 'пешком', f
        elif phase == 'пешком':
            tgt = wps[wi]; d = math.hypot(tgt[0] - hx, tgt[1] - hz)
            if (f - t0) % 30 == 0:
                if seg is not None and cmd_ang is not None:
                    ddx, ddz = hx - seg[0], hz - seg[1]
                    if math.hypot(ddx, ddz) > 0.4 and not side_win: cam = D.ang(math.atan2(ddx, ddz) - cmd_ang)
                cmd_ang = D.ang(math.atan2(tgt[0] - hx, tgt[1] - hz) - cam) if cam is not None else 0.0; side_win = False
            if (f - t0) % 30 == 10: seg = (hx, hz)
            hist.append((hx, hz)); hist[:] = hist[-11:]
            if f > side_until and len(hist) == 11 and math.hypot(hx - hist[0][0], hz - hist[0][1]) < 0.3: side_until = f + 40; side = -side
            if f <= side_until: side_win = True
            an = (cmd_ang or 0.0) + (side * math.pi / 2 if f <= side_until else 0.0)
            cmds = [*D.axis('l', 'y', math.cos(an)), *D.axis('l', 'x', math.sin(an))]
            if d < (0.9 if wi == len(wps) - 1 else 1.2):
                if wi < len(wps) - 1: wi += 1
                else: phase, t0 = 'внутри', f; cmds = [*D.axis('l', 'y', 0.0), *D.axis('l', 'x', 0.0)]
            if f - t0 > 2500: phase, t0 = 'внутри', f
        elif phase == 'внутри' and a.inside and f - t0 > 150 and math.hypot(hx - dx, hz - dz) > 100:   # вошли (Гомер в интерьере)
            phase, t0 = 'пешком внутри', f; wps = [tuple(a.inside)]; wi = 0; cam = cmd_ang = seg = None; hist = []; side_until = -1
        elif phase == 'пешком внутри':
            tgt = wps[wi]; d = math.hypot(tgt[0] - hx, tgt[1] - hz)
            if (f - t0) % 30 == 0:
                if seg is not None and cmd_ang is not None:
                    ddx, ddz = hx - seg[0], hz - seg[1]
                    if math.hypot(ddx, ddz) > 0.4 and not side_win: cam = D.ang(math.atan2(ddx, ddz) - cmd_ang)
                cmd_ang = D.ang(math.atan2(tgt[0] - hx, tgt[1] - hz) - cam) if cam is not None else 0.0; side_win = False
            if (f - t0) % 30 == 10: seg = (hx, hz)
            hist.append((hx, hz)); hist[:] = hist[-11:]
            if f > side_until and len(hist) == 11 and math.hypot(hx - hist[0][0], hz - hist[0][1]) < 0.3: side_until = f + 40; side = -side
            if f <= side_until: side_win = True
            an = (cmd_ang or 0.0) + (side * math.pi / 2 if f <= side_until else 0.0)
            cmds = [*D.axis('l', 'y', math.cos(an)), *D.axis('l', 'x', math.sin(an))]
            if d < 1.0 or f - t0 > 1500: phase, t0 = 'действие внутри', f; cmds = [*D.axis('l', 'y', 0.0), *D.axis('l', 'x', 0.0)]
        elif phase == 'действие внутри':
            for item in a.seq2.split(','):
                b, at = item.split('@'); dur = 6
                if '+' in at: at, dur = at.split('+'); dur = int(dur)
                at = int(at)
                if at <= f - t0 < at + dur: cmds.append(f'pad {b} 1')
                elif at + dur <= f - t0 < at + dur + 2: cmds.append(f'pad {b} 0')
            if f - t0 > a.after: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        elif phase == 'внутри':
            for item in a.seq.split(','):
                b, at = item.split('@'); dur = 6
                if '+' in at: at, dur = at.split('+'); dur = int(dur)
                at = int(at)
                if at <= f - t0 < at + dur: cmds.append(f'pad {b} 1')
                elif at + dur <= f - t0 < at + dur + 2: cmds.append(f'pad {b} 0')
            if f - t0 > a.after: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        if f % a.png == 0 and (phase in ('внутри', 'пешком', 'пешком внутри', 'действие внутри') or f % 200 == 0): cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f'{f}\t{phase}\t{x:.2f}\t{z:.2f}\t{v:.2f}\t{hx:.2f}\t{hz:.2f}' + (f"\t{s['camx']:.2f}\t{s['camy']:.2f}\t{s['camz']:.2f}\t{s['camfx']:.3f}\t{s['camfy']:.3f}\t{s['camfz']:.3f}" if a.cam else '') + '\n')
        if f > 20000: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close(); print(f'фаза {phase}, кадр {o.frame} → {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
