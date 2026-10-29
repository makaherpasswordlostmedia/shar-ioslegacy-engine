#!/usr/bin/env python3
"""Вариант tools/twins/rampjump.py с колонками Wheel (w0..w3: +0x10 off, +0x14 off2 = смещение колеса со знаком, зажато ±0,2662; +0x34 A, +0x35 B; адреса ps2-native-wheel-field-binding.yaml). Запуск как у rampjump.py, --out АБСОЛЮТНЫЙ путь.

Близнецы · правка Роба 342: прыжок оригинала с трамплина (свой PCSX2 без окна, без звука, пустое рисование).
По дорогам до точки разгона (кромка − runup по курсу), разгон по прямой с газом до --kmh (газ отпускается на этой скорости;
--kmh 200 — газ до упора), через кромку и --after кадров полёта и посадки; трасса jump.tsv каждые 2 кадра.
Отличия от tools/twins/jump.py: любое стартовое состояние (--state) — откуда ехать, берётся из первой строки трассы;
в трассе vy (car_vel[1]), y центра масс (car_cm[1]), тангаж (строка 2 матрицы, mat[9]) и путь по линии от кромки;
снимок в точке разгона (--save-stage), повтор с него (--state СНИМОК --stage-state). Эталон гейта — tools/twins/jumpref.py.
  python3 tools/twins/rampjump.py --lip X Y Z --heading ГРАД --kmh 70 --runup 60 --out DIR [--state P2S] [--save-stage P2S] [--stage-state]
Оси оригинала (z = −z движка); курс atan2(нос.x, нос.z), 0° = +z. Заезды правки 342 (05.10, кромки — build/sandbox/routes-l1.tsv):
  jumpzone16: --lip -120.5 3.12 -554.33 --heading 0   (старт build/twins/o4/b2_loop/snap_12000.p2s)
  jumpzone17: --lip 121.37 8.71 -213.02 --heading 180 (старт build/ps2ref/state_l1_incar.p2s)
  jumpzone2:  --lip -53.76 4.21 -629.42 --heading -90 (snap_12000)    jumpzone4: --lip -119.46 10.56 -439.05 --heading 0 (snap_12000)
  скорости --kmh 50 / 70 / 100 / 200, --runup 60; с каждого трамплина первый заезд с --save-stage, остальные с него."""
import argparse, math, subprocess, sys, re
from pathlib import Path
TW = Path(__file__).resolve().parent
sys.path.insert(0, str(TW))
import common as C, orig2, route as R, drive as D

ANSI = re.compile(r'\x1b\[[0-9;]*m')
COLS = list(D.TRACE) + [('vy', 0xa218b4, 'f32'), ('cmy', 0x1298888, 'f32'), ('ny', 0xa21894, 'f32')]
NAMES = ['w0_off', 'w0_off2', 'w0_A', 'w0_B', 'w1_off', 'w1_off2', 'w1_A', 'w1_B', 'w2_off', 'w2_off2', 'w2_A', 'w2_B', 'w3_off', 'w3_off2', 'w3_A', 'w3_B']
COLS += [('w0_off', 10629200, 'f32'), ('w0_off2', 10629204, 'f32'), ('w0_A', 10629236, 'u8'), ('w0_B', 10629237, 'u8'), ('w1_off', 10629344, 'f32'), ('w1_off2', 10629348, 'f32'), ('w1_A', 10629380, 'u8'), ('w1_B', 10629381, 'u8'), ('w2_off', 10629488, 'f32'), ('w2_off2', 10629492, 'f32'), ('w2_A', 10629524, 'u8'), ('w2_B', 10629525, 'u8'), ('w3_off', 10629632, 'f32'), ('w3_off2', 10629636, 'f32'), ('w3_A', 10629668, 'u8'), ('w3_B', 10629669, 'u8')]


class Orig:
    def __init__(self, out, state, null=True):
        orig2.prepare(); self.out = Path(out); self.out.mkdir(parents=True, exist_ok=True)
        sc = self.out / 'script.txt'
        sc.write_text('0 trace - 1 ' + ' '.join(f'{a:x}:{t}' for _, a, t in COLS) + '\n')
        args = ['nice', '-n', '10', str(orig2.BIN), '-statefile', str(state), '-script', str(sc), '-lockstep', '2',
                '-bios', 'scph10000.bin', '-renderer', 'sw', '-swthreads', '1', '-set', 'SPU2/Output/Backend=Null']
        if null: args += ['-set', 'EmuCore/GS/Renderer=11']
        args += ['--', str(orig2.ISO)]
        self.log = (self.out / 'log.txt').open('w')
        self.p = subprocess.Popen(args, cwd=str(self.out), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.frame = 0

    def step(self):
        for line in self.p.stdout:
            line = ANSI.sub('', line)
            if line.startswith('STEP '):
                f = line.split(); self.frame = int(f[1])
                return {n: (float(v) if t == 'f32' else int(v)) for (n, _, t), v in zip(COLS, f[2:])}
            self.log.write(f'[кадр {self.frame}] {line}')
        return None

    def send(self, *cmds):
        for c in cmds: self.p.stdin.write(c + '\n')
        self.p.stdin.write('go\n'); self.p.stdin.flush()

    def end(self):
        try: self.p.stdin.write('end\n'); self.p.stdin.flush()
        except (BrokenPipeError, ValueError): pass
        try: self.p.wait(timeout=60)
        except subprocess.TimeoutExpired: self.p.kill()
        for line in (self.p.stdout or []): self.log.write(ANSI.sub('', line))
        self.log.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lip', type=float, nargs=3, required=True); ap.add_argument('--heading', type=float, required=True)
    ap.add_argument('--kmh', type=float, default=100); ap.add_argument('--runup', type=float, default=60)
    ap.add_argument('--out', required=True); ap.add_argument('--after', type=int, default=200)
    ap.add_argument('--state', default=str(C.DATA / 'build/ps2ref/state_l1_incar.p2s'))
    ap.add_argument('--save-stage', default=None); ap.add_argument('--stage-state', action='store_true', help='состояние уже в точке разгона')
    ap.add_argument('--pre', type=float, nargs='*', default=None, help='доп. точки маршрута x z ... перед точкой разгона')
    ap.add_argument('--png', action='store_true'); a = ap.parse_args()
    hd = math.radians(a.heading); fx, fz = math.sin(hd), math.cos(hd)
    lx, ly, lz = a.lip; stage = (lx - fx * a.runup, lz - fz * a.runup)
    o = Orig(a.out, a.state, null=not a.png)
    if a.png: (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'jump.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\tvy\tcmy\tфаза\talong\tтангаж\tw0_off\tw0_off2\tw0_A\tw0_B\tw1_off\tw1_off2\tw1_A\tw1_B\tw2_off\tw2_off2\tw2_A\tw2_B\tw3_off\tw3_off2\tw3_A\tw3_B\n')
    s = o.step(); x0, z0 = s['x'], s['z']
    pts = None
    if not a.stage_state:
        dests = [('старт', x0, s['y'], z0)]
        pre = list(zip(a.pre[0::2], a.pre[1::2])) if a.pre else []
        pts, _ = R.route_roads(dests + [('разгон', stage[0], 4.0, stage[1])])
        pts = [(x0, s['y'], z0)] + pts + [(px, 4.0, pz) for px, pz in pre] + [(stage[0], 4.0, stage[1])]
        pts, _ = R.resample(pts, 3.0)
    phase = 'разгон' if a.stage_state else 'дорога'; i = stuck = rev = 0; last = t0 = 0; vt = a.kmh / 3.6; saved = False
    while s is not None:
        f = o.frame; x, y, z = s['x'], s['y'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz']); cmds = []
        along = (x - lx) * fx + (z - lz) * fz
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
            near_end = math.hypot(stage[0] - x, stage[1] - z) < 20 and stuck >= 40
            if math.hypot(stage[0] - x, stage[1] - z) < 6 or i >= len(pts) - 2 or near_end:
                phase, t0 = 'разгон', f
                if a.save_stage and not saved: cmds.append(f'save {a.save_stage}'); saved = True
        elif phase == 'разгон':
            tx, tz = lx + fx * (min(along, 0) + 15), lz + fz * (min(along, 0) + 15)
            err = D.ang(math.atan2(tx - x, tz - z) - h); st = max(-1.0, min(1.0, err * 2.0))
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', 'pad circle 0']
            if along >= 0: phase, t0 = 'полёт', f
            if f - t0 > 1500: phase, t0 = 'полёт', f
        elif phase == 'полёт':
            cmds = [*D.axis('l', 'x', 0.0), f'pad cross {1 if v < vt else 0}', 'pad circle 0']
            if f - t0 > a.after: break
        if a.png and phase != 'дорога' and f % 2 == 0: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f"{f}\t{x:.3f}\t{y:.3f}\t{z:.3f}\t{math.degrees(h):.2f}\t{v:.3f}\t{s['vy']:.3f}\t{s['cmy']:.3f}\t{phase}\t{along:.2f}\t{math.degrees(math.asin(max(-1.0, min(1.0, s["ny"])))):.2f}\t"+"\t".join(str(s[n]) for n in NAMES)+"\n")
        if f > 20000: break
        o.send(*cmds); s = o.step()
    tsv.close(); o.end(); print(f'фаза {phase}, кадр {o.frame} → {o.out}')


if __name__ == '__main__':
    main()
