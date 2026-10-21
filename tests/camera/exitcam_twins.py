#!/usr/bin/env python3
"""Правка Роба 167: камера при выходе из машины и посадке, камера пешком — порт против оригинала (близнецы, слово Роба 02.10).
Оригинал: build/twins/o4/v23_exit_cam/walk.tsv — камера PS2 по кадрам (cam_pos 0x7aaba0, cam_fwd 0x7aabb8) и Гомер
(0xa24a70..78), прогон у дома: выход («треугольник» на кадре 60), отход, посадка
  python3 tools/twins/walk.py --to 210 -165 213.9 -170.4 --seq triangle@0 --png 5 --after 300 --cam --out v23_exit_cam
Порт: EBOOT в своём PPSSPPHeadless без окна, сценарий tests/camera/exitcam_scenario.txt («flag camlog»: строки CAMF каждый кадр).
Сверка:
  1. камера пешком стоя после выхода — как у оригинала: 6,45 м за Гомером по горизонтали (±0,15), глаз на 2,38 м над ступнями
     (±0,08), взгляд вниз (fwd.y −0,209 ±0,012);
  2. угол кадра пешком — HOMER_CAM_FOVY 54° (±1,5): вертикаль 4:3 камеры оригинала. Улика (не пересчитывается здесь):
     build/twins/scen/full/camfov — кадры порта в позе камеры PS2 (сценарий «cam») против кадров PS2 (v27_camfov): совпадение
     при 42–44° в широком кадре PS2, который держит горизонталь (у будки — 80° данных) => горизонталь пешком ~68,6° => 4:3 — 54°;
  3. выход плавный: ни одного скачка глаза больше 0,6 м за кадр от последнего кадра камеры машины до позы пешком; поза пешком
     устанавливается за 0,6–1,6 с после того, как Гомер вышел (оригинал: ~0,8 с опуститься, ~1,2 с облететь за спину);
  4. посадка плавная: от позы пешком до камеры машины без скачков больше 0,6 м за кадр.

  python3 tests/camera/exitcam_twins.py [--eboot viewer/build/EBOOT.PBP]   зелёный
  python3 tests/camera/exitcam_twins.py --negative [--eboot ...]          красный: «flag footcamold» (прежняя камера 4,2 м, 62°)
  python3 tests/camera/exitcam_twins.py --check smoke.txt"""
import argparse, math, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins'))
ORIG = ROOT / 'build/twins/o4/v23_exit_cam/walk.tsv'
FOOT_FOVY = 54.0


def original():
    rows = []
    for l in ORIG.read_text().splitlines()[1:]:
        c = l.split('\t')
        if len(c) < 14: continue
        f = int(c[0]); hx, hz, hy = float(c[1]), float(c[2]), float(c[13]); e = [float(x) for x in c[7:10]]; d = [float(x) for x in c[10:13]]
        rows.append(dict(f=f, ph=c[4], dist=math.hypot(e[0] - hx, e[2] - hz), camh=e[1] - hy, fy=d[1]))
    return rows


def port(smoke):
    rows = []
    for l in Path(smoke).read_text(errors='replace').splitlines():
        m = re.match(r'CAMF t=([\d.]+) st=(-?\d+) fov=([\d.]+) eye=([-\d.,]+) look=([-\d.,]+) homer=([-\d.,]+) car=', l)
        if not m: continue
        e = [float(x) for x in m.group(4).split(',')]; k = [float(x) for x in m.group(5).split(',')]; h = [float(x) for x in m.group(6).split(',')]
        d = [k[i] - e[i] for i in range(3)]; n = math.sqrt(sum(x * x for x in d)) or 1.0
        rows.append(dict(t=float(m.group(1)), st=int(m.group(2)), fov=float(m.group(3)), e=e, h=h,
                         dist=math.hypot(e[0] - h[0], e[2] - h[2]), camh=e[1] - h[1], fy=d[1] / n))
    return rows


def check(smoke, expect_red=False):
    O = original(); P = port(smoke); bad = []
    def done(ok_msg):
        if bad:
            print(('КРАСНЫЙ (ожидаемо): ' if expect_red else 'ПРОВАЛ: ') + '; '.join(bad)); return 0 if expect_red else 1
        if expect_red: print('ПРОВАЛ ГЕЙТА: красный прогон прошёл сверку'); return 1
        print(ok_msg); return 0
    if not P: bad.append('нет строк CAMF (flag camlog)'); return done('')
    st_o = [r for r in O if 175 <= r['f'] <= 210]
    od = sum(r['dist'] for r in st_o) / len(st_o); oh = sum(r['camh'] for r in st_o) / len(st_o); of = sum(r['fy'] for r in st_o) / len(st_o)
    i_out = next(i for i in range(1, len(P)) if P[i]['st'] == 0 and P[i - 1]['st'] != 0)   # Гомер вышел
    t_out = P[i_out]['t']
    stand = [r for r in P[i_out:] if t_out + 1.8 <= r['t'] <= t_out + 3.0 and r['st'] == 0]
    pd = sum(r['dist'] for r in stand) / len(stand); ph = sum(r['camh'] for r in stand) / len(stand)
    pf = sum(r['fy'] for r in stand) / len(stand); pfov = sum(r['fov'] for r in stand) / len(stand)
    print(f'оригинал стоя: {od:.2f} м за Гомером, глаз {oh:.2f} м, fwd.y {of:.3f}')
    print(f'порт стоя:     {pd:.2f} м, глаз {ph:.2f} м, fwd.y {pf:.3f}, угол кадра {pfov:.1f}° (норма {FOOT_FOVY:.0f}°)')
    if abs(pd - od) > .15: bad.append(f'дальность {pd:.2f} против {od:.2f} м')
    if abs(ph - oh) > .08: bad.append(f'высота глаза {ph:.2f} против {oh:.2f} м')
    if abs(pf - of) > .012: bad.append(f'наклон {pf:.3f} против {of:.3f}')
    if abs(pfov - FOOT_FOVY) > 1.5: bad.append(f'угол кадра {pfov:.1f}° против {FOOT_FOVY:.0f}°')
    # 3. выход: от последнего кадра камеры машины до установившейся позы пешком
    i_car = i_out - 1
    while i_car > 0 and P[i_car]['st'] == 7: i_car -= 1   # HS_GET_OUT — ещё камера машины
    seg = P[i_car:i_out + 200]
    jump = max(math.dist(a['e'], b['e']) for a, b in zip(seg, seg[1:]))
    fin = stand[0]['e'] if stand else P[-1]['e']
    t_set = next((r['t'] for r in P[i_out:] if math.dist(r['e'], fin) < .05 and r['t'] > t_out), None)
    tset = (t_set - t_out) if t_set is not None else 99.0
    print(f'выход:         скачок глаза за кадр до {jump:.2f} м, поза пешком за {tset:.2f} с после выхода')
    if jump > .6: bad.append(f'скачок камеры при выходе {jump:.2f} м за кадр')
    if not (.6 <= tset <= 1.6): bad.append(f'поза пешком установилась за {tset:.2f} с (норма 0,6–1,6)')
    # 4. посадка
    i_in = next((i for i in range(i_out + 1, len(P)) if P[i]['st'] == 6 and P[i - 1]['st'] != 6), None)
    if i_in is None: bad.append('посадки в сценарии не было')
    else:
        seg = P[max(0, i_in - 120):i_in + 400]
        jin = max(math.dist(a['e'], b['e']) for a, b in zip(seg, seg[1:]))
        print(f'посадка:       скачок глаза за кадр до {jin:.2f} м')
        if jin > .6: bad.append(f'скачок камеры при посадке {jin:.2f} м за кадр')
    return done('OK: камера пешком и переходы машина <-> пешком как у оригинала')


def run(eboot, negative):
    import common as C, port as PT
    scen = (ROOT / 'tests/camera/exitcam_scenario.txt').read_text()
    if negative: scen = scen.replace('flag camlog\n', 'flag camlog\nflag footcamold\n')
    d, man = PT.stage_full(C.OUT / 'scen', 'exitcam' + ('_red' if negative else ''), scen, 5)
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
