#!/usr/bin/env python3
"""№406 (09.10): эталон положения кузова famil_v из уже снятых записей PS2 → tests/cars/attitude_ps2.tsv (гейт tests/cars/attitude.c).
Источники (только чтение): build/codex-terminal/rob-rest/388/*/*/trace.json — свой PCSX2, полная матрица кузова 0x1298ab8 (pm0..15)
и скорость 0xa218b0 каждые 2 кадра (50 к/с); фазы бота tools/twins/contact_slope.py: aim (газ и руль), brake (○ до остановки, руль 0).
Крен и тангаж берутся относительно земли порта под машиной (tests/cars/ground_normal.c), ускорения — разностью скоростей.
  крен:   ровные отсчёты (|Δa_бок| < 3 за 4 кадра, |a_прод| < 6, все колёса: высота начала модели 0,69 ± 0,05, v > 5) — медиана
          крен/a_бок по корзинам |a_бок| 6–9, 9–12, 12–15, 15–25 м/с² (наружу +);
  тангаж: v > 5, |a_бок| < 3: средний тангаж в корзинах a_прод (−25…−12, −12…−6, 2…6) минус накат (−2…2) → отношение °/(м/с²);
  тормоз: заезды фазы brake от v > 6 м/с до 3 м/с — средний темп м/с²;
  поворот: build/twins/o4/{b2_loop,b2_loop2,v28_drive_cam,drive_test,drive_test2}/drive.tsv — руль до упора ≥ 0,48 с без тормоза и
          ручника, 13–17 м/с: медиана и квартили скорости рыскания, 90-й перцентиль угла скольжения.
  python3 tools/twins/attitude_ref.py [--level build/level.shr] [--out tests/cars/attitude_ps2.tsv]"""
import argparse, glob, json, math, re, statistics as S, subprocess, sys
from pathlib import Path


def ground(level, pts, tool):
    out = subprocess.run([tool, level], input=''.join('%f %f %f\n' % p for p in pts), capture_output=True, text=True, check=True).stdout.split('\n')
    return [tuple(map(float, l.split())) for l in out[:len(pts)]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', default='build/level.shr'); ap.add_argument('--out', default='tests/cars/attitude_ps2.tsv'); a = ap.parse_args()
    tool = '/tmp/attitude_ground_normal'
    subprocess.run(['cc', '-O2', '-w', '-I', 'viewer', 'tests/cars/ground_normal.c', 'viewer/col.c', '-lm', '-o', tool], check=True)
    seen, S_, runs, files = set(), [], [], []
    for f in sorted(glob.glob('build/codex-terminal/rob-rest/388/*/*/trace.json')):
        R = json.load(open(f))
        if not R or 'pm0' not in R[0]: continue
        key = (len(R), R[5]['pm12'])
        if key in seen: continue   # повторы одного прогона (кэш близнеца)
        seen.add(key); files.append(f); pts = []
        for i in range(2, len(R) - 2):
            p0, b, c = R[i - 1], R[i], R[i + 1]; dt = (c['rel'] - p0['rel']) / 50.0
            p2, c2 = R[i - 2], R[i + 2]; dt2 = (c2['rel'] - p2['rel']) / 50.0
            if dt <= 0 or dt > 0.1 or dt2 <= 0: continue
            L = (-b['pm0'], -b['pm1'], b['pm2']); F = (b['pm8'], b['pm9'], -b['pm10'])
            acc = ((c['vx'] - p0['vx']) / dt, (c['vy'] - p0['vy']) / dt, -(c['vz'] - p0['vz']) / dt)
            acc2 = ((c2['vx'] - p2['vx']) / dt2, (c2['vy'] - p2['vy']) / dt2, -(c2['vz'] - p2['vz']) / dt2)
            d = lambda u, v: u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
            pts.append(dict(v=math.hypot(b['vx'], b['vz']), vy=b['vy'], alat=d(acc, L), alat2=d(acc2, L), alon=d(acc, F), alon2=d(acc2, F),
                            L=L, F=F, pos=(b['pm12'], b['pm13'], -b['pm14'])))
        for p, (ok, nx, ny, nz, gy) in zip(pts, ground(a.level, [p['pos'] for p in pts], tool)):
            n = (nx, ny, nz); p['ok'] = ok > 0; p['h'] = p['pos'][1] - gy
            p['roll'] = math.degrees(math.asin(max(-1, min(1, sum(x * y for x, y in zip(p['L'], n))))))
            p['pitch'] = math.degrees(math.asin(max(-1, min(1, sum(x * y for x, y in zip(p['F'], n))))))
        S_ += pts
        seg = []
        for p0, b in zip(R, R[1:]):
            if p0.get('phase') == 'brake' and b.get('phase') == 'brake':
                v0 = math.hypot(p0['vx'], p0['vz'])
                if not seg and v0 > 6: seg = [(p0['rel'], v0)]
                elif seg and v0 <= 3: runs.append((seg[0][1], (p0['rel'] - seg[0][0]) / 50.0)); seg = []
            else: seg = []
    flat = [p for p in S_ if p['ok'] and abs(p['h'] - 0.69) < 0.05]
    rows = []
    roll = [p for p in flat if p['v'] > 5 and abs(p['alon']) < 6 and abs(p['alat'] - p['alat2']) < 3 and abs(p['vy']) < 1]
    for lo, hi in [(6, 9), (9, 12), (12, 15), (15, 25)]:
        s = [p['roll'] / p['alat'] for p in roll if lo <= abs(p['alat']) < hi]
        rows.append(('roll_grad', f'{lo}-{hi}', len(s), S.median(s)))
    pit = [p for p in flat if p['v'] > 5 and abs(p['alat']) < 3 and abs(p['alon'] - p['alon2']) < 2 and abs(p['vy']) < 0.7]
    coast = S.mean(p['pitch'] for p in pit if -2 <= p['alon'] < 2)
    for name, lo, hi in [('pitch_brake', -25, -12), ('pitch_brake', -12, -6), ('pitch_gas', 2, 6)]:
        s = [p for p in pit if lo <= p['alon'] < hi]
        rows.append((name, f'{lo}..{hi}', len(s), (S.mean(p['pitch'] for p in s) - coast) / S.mean(p['alon'] for p in s)))
    for v0, t in runs: rows.append(('brake_run', f'{v0:.1f}', 1, (3 - v0) / t))
    yaw, slip, vs = [], [], []
    for dname in ['b2_loop', 'b2_loop2', 'v28_drive_cam', 'drive_test', 'drive_test2']:
        R = [l.rstrip('\n').split('\t') for l in open(f'build/twins/o4/{dname}/drive.tsv', encoding='utf-8')]
        ix = {k: i for i, k in enumerate(R[0])}; R = [r for r in R[1:] if len(r) > ix['кнопки']]
        def stick(r):
            m = re.search(r'l(left|right) ([0-9.]+)', r[ix['кнопки']]); return (1 if m and m.group(1) == 'left' else -1) * float(m.group(2)) if m else 0.0
        for i in range(12, len(R) - 2):
            w = R[i - 12:i + 1]
            if not all(abs(stick(r)) >= 0.95 and 'square' not in r[ix['кнопки']] and 'circle' not in r[ix['кнопки']] for r in w): continue
            if len({stick(r) > 0 for r in w}) > 1: continue
            p0, b = R[i - 1], R[i + 1]; dt = (int(b[0]) - int(p0[0])) / 50
            v = float(R[i][ix['v']])
            if dt <= 0 or dt > 0.1 or not 13 <= v <= 17: continue
            yaw.append(abs((float(b[ix['курс']]) - float(p0[ix['курс']]) + 180) % 360 - 180) / dt); vs.append(v)
            mv = math.degrees(math.atan2(float(b[1]) - float(p0[1]), float(b[3]) - float(p0[3])))
            slip.append(abs((mv - float(R[i][ix['курс']]) + 180) % 360 - 180))
    q = S.quantiles(yaw, n=4)
    rows += [('yaw_15', 'median', len(yaw), S.median(yaw)), ('yaw_15', 'q1', len(yaw), q[0]), ('yaw_15', 'q3', len(yaw), q[2]),
             ('slip_15', 'p90', len(slip), S.quantiles(slip, n=10)[8]), ('yaw_15', 'v_median', len(vs), S.median(vs))]
    lines = ['# №406: положение кузова famil_v у PS2 (tools/twins/attitude_ref.py; записи: ' + ', '.join(Path(f).parent.relative_to('build/codex-terminal/rob-rest/388').as_posix() for f in files) + ' и drive.tsv b2_loop, b2_loop2, v28_drive_cam, drive_test, drive_test2)',
             '# величина\tкорзина\tотсчётов\tзначение (крен °/(м/с²) наружу +; тангаж °/(м/с²) нос вверх + при a>0; тормоз м/с²; рыскание °/с; скольжение °; v_median — скорость тех же отсчётов, м/с)']
    lines += ['%s\t%s\t%d\t%.4f' % r for r in rows]
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print('\n'.join(lines))


if __name__ == '__main__':
    main()
