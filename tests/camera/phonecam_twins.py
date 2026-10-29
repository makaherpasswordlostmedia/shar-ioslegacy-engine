#!/usr/bin/env python3
"""Правка Роба 166: облёт камеры у будки после вызова машины — порт против оригинала (близнецы, слово Роба 02.10: «собрал для
PSP — сразу узнал у эмулятора PS2»).
Оригинал: build/twins/o4/v12_booth_cam/walk.tsv — камера PS2 по кадрам (cam_pos 0x7aaba0, cam_fwd 0x7aabb8), прогон
  python3 tools/twins/walk.py --to 228.7 -149.6 --seq triangle@0,cross@80 --png 10 --after 400 --cam --out v12_booth_cam
  (будка Z1p1 у дома, Family Sedan, ~4 мин, свой PCSX2 без окна).
Порт: EBOOT в своём PPSSPPHeadless без окна (tools/twins/port.py), сценарий tests/camera/phonecam_scenario.txt (Гомер у Z1p1,
«треугольник», Accept), строки PHONECAM smoke.txt — каждый кадр облёта: время облёта, глаз, точка взгляда.
Сверка: кадры облёта оригинала (взгляд вниз на 0,131, как в анимации phonecamera.p3d) против порта в тот же момент облёта
по времени от смены камеры (сдвиг до ±0,1 с, темп 0,95–1,05): глаз до 5 см, направление взгляда до 2,5°; облёт кончился сам.

  python3 tests/camera/phonecam_twins.py [--eboot viewer/build/EBOOT.PBP]   зелёный
  python3 tests/camera/phonecam_twins.py --negative [--eboot ...]          красный: flag phoneplant (оси матрицы будки без
                                                                            поворота на 90°) — сверка обязана упасть
  python3 tests/camera/phonecam_twins.py --check smoke.txt                 только сверка готового прогона"""
import argparse, math, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins'))
ORIG = ROOT / 'build/twins/o4/v12_booth_cam/walk.tsv'
EYE_TOL, ANG_TOL, PAL_HZ = 0.05, 2.5, 50.0


def original():
    rows = []
    for l in ORIG.read_text().splitlines()[1:]:
        c = l.split('\t')
        if len(c) < 13: continue
        f = int(c[0]); e = [float(x) for x in c[7:10]]; d = [float(x) for x in c[10:13]]
        rows.append((f, (e[0], e[1], -e[2]), (d[0], d[1], -d[2])))   # оси порта: z = −z оригинала
    return rows


def port(smoke):
    out, ended = [], False
    for l in Path(smoke).read_text(errors='replace').splitlines():
        m = re.match(r'PHONECAM t=[\d.]+ pt=([\d.]+) at=[\d.]+ booth=(\S+) eye=([-\d.,]+) look=([-\d.,]+)', l)
        if m:
            e = [float(x) for x in m.group(3).split(',')]; k = [float(x) for x in m.group(4).split(',')]
            d = [k[i] - e[i] for i in range(3)]; n = math.sqrt(sum(x * x for x in d)) or 1.0
            out.append((float(m.group(1)), m.group(2), e, [x / n for x in d]))
        if l.startswith('PHONECAM end'): ended = True
    return out, ended


def at(P, t):   # поза порта в момент облёта t (линейно между кадрами)
    if t <= P[0][0]: return P[0][2], P[0][3]
    for a, b in zip(P, P[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / max(b[0] - a[0], 1e-6)
            e = [a[2][i] + (b[2][i] - a[2][i]) * u for i in range(3)]; d = [a[3][i] + (b[3][i] - a[3][i]) * u for i in range(3)]
            n = math.sqrt(sum(x * x for x in d)); return e, [x / n for x in d]
    return P[-1][2], P[-1][3]


def ang(a, b): return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


def check(smoke, expect_red=False):
    O = original(); P, ended = port(smoke)
    def fail(msg):
        print(('КРАСНЫЙ (ожидаемо): ' if expect_red else 'ПРОВАЛ: ') + msg); return 0 if expect_red else 1
    if not P: return fail('в smoke.txt нет PHONECAM — облёт будки не играл')
    booth = {p[1] for p in P}
    if booth != {'Z1p1'}: return fail(f'облёт у будки {booth}, оригинал снят у Z1p1')
    e0 = P[0][2]
    # кадры облёта оригинала: взгляд вниз как в анимации (fwd.y ≈ −0.131) и глаз рядом с первым кадром облёта оригинала
    A = [r for r in O if abs(r[2][1] + 0.131) < 0.004]
    if len(A) < 20: return fail(f'в записи оригинала мало кадров облёта ({len(A)})')
    f0 = A[0][0]; A = [r for r in A if math.dist(r[1], A[0][1]) < 1.0]
    span_o = (A[-1][0] - f0) / PAL_HZ
    best = None
    for ks in range(95, 106):
        k = ks / 100.0
        for ds in range(-10, 11):
            dl = ds / 100.0
            ee = aa = 0.0
            for f, e, d in A:
                pe, pd = at(P, (f - f0) / PAL_HZ * k + dl)
                ee = max(ee, math.dist(pe, e)); aa = max(aa, ang(pd, d))
            if best is None or (aa, ee) < (best[0], best[1]): best = (aa, ee, k, dl)
    aa, ee, k, dl = best
    print(f'оригинал: {len(A)} кадров облёта (с {f0}, {span_o:.2f} с PAL), глаз {tuple(round(x, 3) for x in A[0][1])}')
    print(f'порт:     {len(P)} кадров, облёт {P[-1][0]:.2f} с, конец сам: {ended}, глаз {tuple(round(x, 3) for x in e0)}')
    print(f'сверка:   глаз до {ee:.3f} м (допуск {EYE_TOL}), взгляд до {aa:.2f}° (допуск {ANG_TOL}), темп {k:.2f}, сдвиг {dl:.2f} с')
    bad = []
    if ee > EYE_TOL: bad.append(f'глаз расходится на {ee:.2f} м')
    if aa > ANG_TOL: bad.append(f'взгляд расходится на {aa:.1f}°')
    if not ended: bad.append('облёт не кончился сам')
    if bad: return fail('; '.join(bad))
    if expect_red: print('ПРОВАЛ ГЕЙТА: красный прогон прошёл сверку'); return 1
    print('OK: облёт будки как у оригинала'); return 0


def run(eboot, negative):
    import common as C, port as PT
    scen = (ROOT / 'tests/camera/phonecam_scenario.txt').read_text()
    if negative: scen = scen.replace('flag msn\n', 'flag msn\nflag phoneplant\n')
    d, man = PT.stage_full(C.OUT / 'scen', 'phonecam' + ('_red' if negative else ''), scen, 5)
    if eboot: (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(PT.HEADLESS), '--graphics=software', '--timeout=300', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        PT.watch_no_window(pr, 360)
    for b in sorted(d.glob('*.bmp')): PT.bmp_to_png(b, b.with_suffix('.png'))
    print(f'прогон: {d.relative_to(ROOT)} (EBOOT {C.sha256(d / "EBOOT.PBP", 16)})')
    return d / 'smoke.txt'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--eboot'); ap.add_argument('--negative', action='store_true'); ap.add_argument('--check')
    a = ap.parse_args()
    if not ORIG.exists(): print(f'нет записи оригинала {ORIG.relative_to(ROOT)} — прогон близнеца из шапки'); return 1
    smoke = Path(a.check) if a.check else run(a.eboot, a.negative)
    return check(smoke, a.negative)


if __name__ == '__main__':
    sys.exit(main())
