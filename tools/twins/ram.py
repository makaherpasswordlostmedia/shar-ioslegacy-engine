#!/usr/bin/env python3
"""Близнецы · В14: сколько ударов выдерживает машина трафика в оригинале. Бот (drive.Original, lockstep) рулит в минивэн трафика,
бьёт с разгона, сдаёт назад, повторяет; каждые 25 кадров — кадр экрана (png), шкала Hit & Run — счётчик контактов (+5 за контакт).

  python3 tools/twins/ram.py [--hits 8] [--frames 6000] → build/twins/o4/v14_ram/: ram.tsv, png/f<кадр>.png
Минивэн — детали машины трафика 0x0eee2f0…: позиция 0x0eee320/24/28 (в этом состоянии он с кадра 0 едет по улице у дома)."""
import argparse, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import drive as D

MV = [('mx', 0xeee320, 'f32'), ('my', 0xeee324, 'f32'), ('mz', 0xeee328, 'f32')]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--hits', type=int, default=8); ap.add_argument('--frames', type=int, default=6000)
    ap.add_argument('--out', default='v14_ram')
    ap.add_argument('--straight', action='store_true'); ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--wav-from', type=int, default=-1); ap.add_argument('--exit-walk', type=int, default=0); a = ap.parse_args()
    ex_t = None   # после серии: выйти («треугольник») и уйти пешком (стик вперёд) — звук разбитой машины (В13)
    o = D.Original(C.OUT / 'o4' / a.out, extra=MV); (o.out / 'png').mkdir(exist_ok=True)
    tsv = (o.out / 'ram.tsv').open('w'); tsv.write('кадр\tx\tz\tv\tмх\tмz\tд\tшкала\tфаза\tудар\n')
    phase, t_phase, hits, prev_h, stuck = 'разгон', 0, 0, 0.0, 0
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        d = math.hypot(s['mx'] - x, s['mz'] - z); err = D.ang(math.atan2(s['mx'] - x, s['mz'] - z) - h)
        if s['hnr'] > prev_h + 2.5 and d < 7: hits += 1; phase, t_phase = 'назад', f
        prev_h = s['hnr']
        st = 0.0 if a.straight else max(-1.0, min(1.0, err * 2.5))
        stuck = stuck + 2 if (phase == 'разгон' and v < 0.8 and f > a.start + 60) else 0
        if stuck >= 50: phase, t_phase, stuck = 'назад', f, 0   # упёрся не в минивэн — тоже назад и заново
        if f < a.start:
            cmds = ['pad cross 0']
        elif phase == 'разгон':
            cmds = [*D.axis('l', 'x', st), 'pad cross 1', 'pad circle 0']
        else:   # назад 1,2 с, руль от цели — отъехать на разбег
            cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -st)]
            if f - t_phase > 60: phase = 'разгон'
        if f == a.wav_from: cmds.append(f"wav {o.out / 'audio.wav'}")
        if ex_t is not None:
            cmds = ['pad cross 0', 'pad circle 0', *D.axis('l', 'x', 0.0)]
            if f - ex_t < 6: cmds.append('pad triangle 1')
            elif f - ex_t < 8: cmds.append('pad triangle 0')
            elif f - ex_t >= 150: cmds += D.axis('l', 'y', 1.0)
            if f - ex_t >= a.exit_walk: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        if f % 25 == 0: cmds.append(f"png {o.out / 'png' / f'f{f:05d}.png'}")
        tsv.write(f"{f}\t{x:.2f}\t{z:.2f}\t{v:.2f}\t{s['mx']:.2f}\t{s['mz']:.2f}\t{d:.2f}\t{s['hnr']:.1f}\t{phase}\t{hits}\n")
        if ex_t is None and (hits >= a.hits and phase == 'разгон' and f - t_phase > 200 or f >= a.frames):
            if a.exit_walk: ex_t = f
            else: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    print(f'ударов {hits}, кадров {o.frame} → {o.out.relative_to(C.DATA)}')


if __name__ == '__main__':
    main()
