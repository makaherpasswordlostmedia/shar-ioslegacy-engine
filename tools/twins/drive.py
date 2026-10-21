#!/usr/bin/env python3
"""Близнецы · О4: бот за рулём оригинала. pcsx2-twins в режиме -lockstep: каждые K кадров оригинал отдаёт позицию и ждёт кнопки —
замкнутый цикл кадр в кадр, без окна, повторяемо (тот же вход → та же поездка).

  python3 tools/twins/drive.py steer       проба руля: 2 с газ, потом стик вправо 1,5 с → в какую сторону поворачивает
  python3 tools/twins/drive.py route --out ID [--speed 20] [--frames N] [--cdvd]   ехать по дорогам L1 (tools/twins/route.py)
Выход build/twins/o4/<ID>/: drive.tsv (кадр, поза, скорость, кнопки), log.txt (журнал эмулятора; с --cdvd — чтения диска с кадром),
snap_*.p2s / shot_*.png по --shots. Время только в кадрах (50 в секунду, PAL)."""
import argparse, json, math, os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import orig2

ANSI = re.compile(r'\x1b\[[0-9;]*m')
TRACE = [('x', 0xa218a0, 'f32'), ('y', 0xa218a4, 'f32'), ('z', 0xa218a8, 'f32'),     # mat[12..14] — начало модели машины
         ('nx', 0xa21890, 'f32'), ('nz', 0xa21898, 'f32'),                            # mat[8], mat[10] — нос машины
         ('vx', 0xa218b0, 'f32'), ('vz', 0xa218b8, 'f32'), ('hnr', 0x612114, 'f32'), ('frame', 0x5167d8, 'u32')]


class Original:
    """один экземпляр оригинала без окна; step() → словарь величин, send() — команды до следующего go"""
    def __init__(self, out, state='build/ps2ref/state_l1_incar.p2s', lockstep=2, cdvd=False, renderer='sw', extra=(), wav=None):
        orig2.prepare(); self.out = Path(out); self.out.mkdir(parents=True, exist_ok=True)
        self.cols = list(TRACE) + list(extra)
        sc = self.out / 'script.txt'
        sc.write_text('0 trace - 1 ' + ' '.join(f'{a:x}:{t}' for _, a, t in self.cols) + '\n' + (f'0 wav {wav}\n' if wav else ''))
        args = ['nice', '-n', '10', str(orig2.BIN), '-statefile', str(C.DATA / state), '-script', str(sc), '-lockstep', str(lockstep),
                '-bios', 'scph10000.bin', '-renderer', renderer, '-swthreads', '2']
        args += ['-set', 'SPU2/Output/Backend=Null']   # без звука: Роб 03.10 «тесты на фоне без звука» (OutputModule=nullout в v2.6 не читается)
        if cdvd: args += ['-set', 'EmuCore/CdvdVerboseReads=true']
        args += ['--', str(orig2.ISO)]
        self.log = (self.out / 'log.txt').open('w')
        self.p = subprocess.Popen(args, cwd=str(self.out), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, bufsize=1)
        self.frame = 0

    def step(self):
        for line in self.p.stdout:
            line = ANSI.sub('', line)
            if line.startswith('STEP '):
                f = line.split(); self.frame = int(f[1])
                return {n: (float(v) if t == 'f32' else int(v)) for (n, _, t), v in zip(self.cols, f[2:])}
            self.log.write(f'[кадр {self.frame}] {line}')
        return None

    def send(self, *cmds):
        for c in cmds: self.p.stdin.write(c + '\n')
        self.p.stdin.write('go\n'); self.p.stdin.flush()

    def close(self):
        try: self.p.stdin.write('end\n'); self.p.stdin.flush()
        except (BrokenPipeError, ValueError): pass
        try: self.p.wait(timeout=60)
        except subprocess.TimeoutExpired: self.p.kill()
        for line in (self.p.stdout or []): self.log.write(f'[кадр {self.frame}] {ANSI.sub("", line)}')
        self.log.close()


def axis(stick, ax, v):
    """ось стика двумя командами: в PCSX2 (PadDualshock2::Set, MERGE) ось берёт ненулевую полуось, «вниз»/«вправо» — первыми;
    оставленная нажатой полуось глушит противоположную. Поэтому всегда: обнулить ненужную полуось и задать нужную"""
    v = max(-1.0, min(1.0, v)); pos, neg = ('right', 'left') if ax == 'x' else ('up', 'down')
    on, off = (pos, neg) if v >= 0 else (neg, pos)
    return [f'pad {stick}{off} 0', f'pad {stick}{on} {abs(v):.3f}']


D_axis = axis


def ang(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def steer_probe():
    o = Original(C.OUT / 'o4' / 'steer_probe'); rows = []
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; h = math.atan2(s['nx'], s['nz'])
        rows.append((f, s['x'], s['z'], h, math.hypot(s['vx'], s['vz'])))
        cmds = ['pad cross 1'] if 20 <= f < 220 else ['pad cross 0']
        cmds += ['pad lright 1'] if 100 <= f < 175 else ['pad lright 0']
        if f >= 260: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close()
    for r in rows[::20]: print(f'{r[0]:4d} ({r[1]:7.2f},{r[2]:8.2f}) курс {math.degrees(r[3]):7.1f}° |v| {r[4]:5.2f}')
    h0 = next(r[3] for r in rows if r[0] >= 98); h1 = next(r[3] for r in rows if r[0] >= 176)
    print(f'стик вправо 1,5 с: курс {math.degrees(h0):.1f}° → {math.degrees(h1):.1f}° (изменение {math.degrees(ang(h1 - h0)):+.1f}°)')


def drive_route(out_id, vmax=18.0, frames=30000, cdvd=False, shots_every=0, lockstep=2, shots_at=(), extra=()):
    """едет по ломаной route.py (оси оригинала): упреждение 12 м, руль пропорционально углу, газ до vmax, застрял — назад"""
    import route as R
    pts, marks = R.route_roads()   # сеть дорог оригинала (перекрёстки и дороги диска), без срезок через дворы
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts   # из дорожки дома сначала прямо на улицу, потом по дорогам
    pts, _ = R.resample(pts, 3.0)
    o = Original(C.OUT / 'o4' / out_id, lockstep=lockstep, cdvd=cdvd, extra=extra)
    tsv = (o.out / 'drive.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\tиндекс\tшкала\tкнопки' + ''.join('\t' + n for n, _, _ in extra) + '\n')
    i = 0; stuck = 0; rev = 0; done = False; last_progress = 0; boost = 0
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        # продвижение по маршруту: ближайшая точка в окне впереди
        best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
        if best > i: i = best; last_progress = f
        if i >= len(pts) - 2 or f >= frames: done = True
        j = min(len(pts) - 1, i + (3 if f > boost else 7))   # упреждение ~9 м; после выхода из тупика — дальше (21 м)
        err = ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
        cmds = []
        if rev > 0:   # манёвр выхода: назад и руль в другую сторону
            rev -= lockstep; cmds = ['pad cross 0', 'pad circle 1', *D_axis('l', 'x', -1.0 if err > 0 else 1.0)]
            if rev <= 0: cmds = ['pad circle 0', *D_axis('l', 'x', 0.0)]; boost = f + 150
        else:
            st = max(-1.0, min(1.0, err * 2.5))
            vt = vmax * max(0.35, math.cos(err))
            cmds = [*D_axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 5 else 0}']
            stuck = stuck + lockstep if v < 0.8 else 0
            if stuck >= 50 or f - last_progress > 500: rev = 60; stuck = 0; last_progress = f
        if (shots_every and f % shots_every == 0 and f) or f in shots_at: cmds.append(f"save {o.out / f'snap_{f}.p2s'}")
        tsv.write(f"{f}\t{x:.2f}\t{s['y']:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{i}\t{s['hnr']:.1f}\t{' '.join(c[4:] for c in cmds if c.startswith('pad') and not c.endswith(' 0') and not c.endswith(' 0.000'))}" +
                  ''.join(f"\t{s[n]:.3f}" for n, _, _ in extra) + "\n")
        if done:
            o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    return o.out, i, len(pts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['steer', 'route'])
    ap.add_argument('--out', default='drive'); ap.add_argument('--speed', type=float, default=18.0)
    ap.add_argument('--frames', type=int, default=30000); ap.add_argument('--cdvd', action='store_true'); ap.add_argument('--shots', type=int, default=0)
    ap.add_argument('--cam', action='store_true', help='камера оригинала (cam_pos, cam_fwd) в drive.tsv — камера машины по кадрам')
    a = ap.parse_args()
    if a.cmd == 'steer': steer_probe(); return 0
    CAM = [('cx', 0x7aaba0, 'f32'), ('cy', 0x7aaba4, 'f32'), ('cz', 0x7aaba8, 'f32'), ('fx', 0x7aabb8, 'f32'), ('fy', 0x7aabbc, 'f32'), ('fz', 0x7aabc0, 'f32'),
           ('nx2', 0xa21890, 'f32'), ('nz2', 0xa21898, 'f32')]
    out, i, n = drive_route(a.out, a.speed, a.frames, a.cdvd, a.shots, extra=CAM if a.cam else ())
    print(f'проехал точек маршрута {i} из {n} → {out.relative_to(C.DATA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
