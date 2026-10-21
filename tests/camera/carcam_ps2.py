#!/usr/bin/env python3
"""Правка Роба 198+ (03.10: «у нас широкая камера, шире, чем в оригинале, это нужно учитывать; школьный автобус закрывает весь
экран, ничего не видно»): камера за машиной — кадр оригинала с поправкой на угол кадра порта (viewer/main.c chaseCamUpdate).

Порт: EBOOT в своём PPSSPPHeadless без окна и звука, сценарий tests/camera/carcam_scenario.txt — famil_v, школьный автобус
schoolbu, грузовик glastruc на прямой улице L1; движок раз в секунду пишет CARCAM: глаз, цель, угол кадра, место и курс машины,
lift модели, кузов (halfW, halfL, bodyOfs, bodyLo, bodyHi — из данных машины).
Эталон PS2 — та же коробка кузова в кадре оригинала: дальний вариант FollowCameraData машины с диска (tools/carcam2h.py; у
оригинала в езде стоит дальний — близнец v28_drive_cam, knowledge/facts/ps2-camera-fov.yaml), глаз от начала модели
(низ колёс + lift), цель — смещение данных; кадр 4:3, 77° по горизонтали (та же карточка).
Сверка по кадру стоя (угол кадра 62°, без обхода стен), для каждой из трёх машин:
  1. доля экрана под кузовом (площадь проекции коробки в кадре) — как у PS2, ±15 %;
  2. дорога видна над крышей: точки дороги в 20 и 30 м перед носом не закрыты кузовом и в кадре.
Красный контроль — «flag camnearold» (прежняя камера: ближний вариант, цель — середина машины на 1,4 м): famil_v на экране в
1,6 раза больше, чем у PS2, у автобуса и грузовика дорога спрятана на 34 и 56 м.

  python3 tests/camera/carcam_ps2.py [--eboot viewer/build/EBOOT.PBP]      зелёный
  python3 tests/camera/carcam_ps2.py --negative [--eboot ...]              красный: прежняя камера
  python3 tests/camera/carcam_ps2.py --check smoke.txt [--expect-red]      только разбор журнала"""
import argparse, math, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins')); sys.path.insert(0, str(ROOT / 'tools'))
CARS = ('famil_v', 'schoolbu', 'glastruc')
PS2_HFOV, PS2_ASPECT = 77.0, 4.0 / 3.0      # knowledge/facts/ps2-camera-fov.yaml: машина ~77° по горизонтали, запись Роба 4:3
SHARE_TOL = 0.15
ROAD = (20.0, 30.0)


def parse(smoke):
    rows = []
    for l in Path(smoke).read_text(errors='replace').splitlines():
        if not l.startswith('CARCAM '): continue
        kv = dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
        vec = lambda k: [float(x) for x in kv[k].split(',')]
        rows.append(dict(t=float(kv['t']), car=kv['car'], ps2=int(kv['ps2']), eye=vec('eye'), look=vec('look'), fovy=float(kv['fovy']),
                         aspect=float(kv['aspect']), pos=vec('pos'), h=float(kv['h']), lift=float(kv['lift']), box=vec('box'),
                         v=float(kv['v']), wall=float(kv['wall'])))
    return rows


def to_local(p, pos, h):
    """мир -> оси машины: x вбок, y вверх от низа колёс, z вперёд (нос = (sin h, cos h))"""
    dx, dy, dz = p[0] - pos[0], p[1] - pos[1], p[2] - pos[2]
    return (dx * math.cos(h) - dz * math.sin(h), dy, dx * math.sin(h) + dz * math.cos(h))


def project(eye, look, P, vfov, aspect):
    f = [look[i] - eye[i] for i in range(3)]; n = math.sqrt(sum(x * x for x in f)); f = [x / n for x in f]
    r = [-f[2], 0.0, f[0]]; n = math.hypot(r[0], r[2]); r = [r[0] / n, 0.0, r[2] / n]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    d = [P[i] - eye[i] for i in range(3)]
    z = sum(d[i] * f[i] for i in range(3)); x = sum(d[i] * r[i] for i in range(3)); y = sum(d[i] * u[i] for i in range(3))
    th = math.tan(math.radians(vfov / 2)); return (x / z / (th * aspect), y / z / th, z)


def hull(pts):
    pts = sorted(set(pts))
    cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def clip_share(poly):
    """доля кадра [-1,1]^2 под многоугольником (отсечение по краям кадра)"""
    for k in (0, 1):
        for s in (1, -1):
            out = []
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                ina, inb = s * a[k] <= 1, s * b[k] <= 1
                if ina: out.append(a)
                if ina != inb:
                    t = (1 - s * a[k]) / (s * b[k] - s * a[k]); out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            poly = out
            if not poly: return 0.0
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) / 8.0


def hits_box(o, p, lo, hi):
    t0, t1 = 0.0, 1.0
    for i in range(3):
        d = p[i] - o[i]
        if abs(d) < 1e-9:
            if not lo[i] <= o[i] <= hi[i]: return False
            continue
        a, b = (lo[i] - o[i]) / d, (hi[i] - o[i]) / d
        if a > b: a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1: return False
    return True


def frame(eye, look, vfov, aspect, box):
    """кадр в осях машины: доля экрана под кузовом, видны ли точки дороги ROAD м перед носом, с какого метра видна дорога"""
    hw, hl, bo, blo, bhi = box
    lo, hi = (-hw, blo, bo - hl), (hw, bhi, bo + hl)
    pts = [project(eye, look, (x, y, z), vfov, aspect) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    share = clip_share(hull([(p[0], p[1]) for p in pts])) if all(p[2] > 0 for p in pts) else 1.0
    def seen(D):
        P = (0.0, 0.0, hi[2] + D); q = project(eye, look, P, vfov, aspect)
        return q[2] > 0 and abs(q[0]) <= 1 and abs(q[1]) <= 1 and not hits_box(eye, P, lo, hi)
    first = next((D / 2 for D in range(1, 241) if seen(D / 2)), None)
    return share, {D: seen(D) for D in ROAD}, first


def ps2_frame(car, row):
    from carcam2h import cams, CARS as DISK
    c = cams(DISK / f'{car}.p3d')
    if not c: return None
    fe, fm, tx, ty, tz = c[1]; lift = row['lift']
    eye = (0.0, lift + fm * math.cos(fe), -fm * math.sin(fe)); look = (tx, lift + ty, tz)
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(PS2_HFOV / 2)) / PS2_ASPECT))
    return frame(eye, look, vfov, PS2_ASPECT, row['box']), eye


def check(smoke, expect_red=False):
    R = parse(smoke); bad = []
    print(f'журнал: {smoke}')
    for car in CARS:
        rows = [r for r in R if r['car'] == car]
        still = [r for r in rows if (abs(r['fovy'] - 62.0) < .3 or abs(r['fovy'] - 55.0) < .3) and r['wall'] > .999 and abs(r['v']) < .5]
        if not still: bad.append(f'{car}: нет кадра стоя (CARCAM без стен)'); continue
        r = still[-1]
        eye, look = to_local(r['eye'], r['pos'], r['h']), to_local(r['look'], r['pos'], r['h'])
        share, road, first = frame(eye, look, r['fovy'], r['aspect'], r['box'])
        ref = ps2_frame(car, r)
        if not ref: bad.append(f'{car}: нет камер на диске'); continue
        (s2, road2, first2), eye2 = ref
        drv = [x for x in rows if abs(x['v']) > 8 and x['wall'] > .999]
        dtxt = ''
        if drv:
            d = drv[-1]; de, dl = to_local(d['eye'], d['pos'], d['h']), to_local(d['look'], d['pos'], d['h'])
            ds, _, dfirst = frame(de, dl, d['fovy'], d['aspect'], d['box'])
            dtxt = f'; в езде {d["v"]:.0f} м/с: {ds * 100:.1f} %, дорога с {dfirst} м'
        print(f'{car:9s} порт{" (правило 198+)" if r["ps2"] else " (прежняя камера)"}: глаз {-eye[2]:.2f} м позади, {eye[1]:.2f} м над низом колёс; '
              f'кузов {share * 100:.1f} % экрана; дорога видна с {first} м перед носом (20 м — {"да" if road[20.0] else "нет"}, '
              f'30 м — {"да" if road[30.0] else "нет"}){dtxt}')
        print(f'{"":9s} PS2 (дальний, 4:3, 77°): глаз {-eye2[2]:.2f} / {eye2[1]:.2f} м; кузов {s2 * 100:.1f} % экрана; дорога с {first2} м')
        if abs(share / s2 - 1) > SHARE_TOL: bad.append(f'{car}: доля экрана {share * 100:.1f} % против {s2 * 100:.1f} % у PS2')
        for D in ROAD:
            if not road[D]: bad.append(f'{car}: дорога в {D:.0f} м перед носом закрыта кузовом')
    if bad:
        print(('КРАСНЫЙ (ожидаемо): ' if expect_red else 'ПРОВАЛ: ') + '; '.join(bad)); return 0 if expect_red else 1
    if expect_red: print('ПРОВАЛ ГЕЙТА: красный прогон прошёл сверку'); return 1
    print('OK: famil_v, автобус и грузовик занимают ту же долю экрана, что у PS2, дорога в 20 и 30 м перед носом видна над крышей')
    return 0


def run(eboot, negative):
    import common as C, port as PT
    scen = (ROOT / 'tests/camera/carcam_scenario.txt').read_text()
    if negative: scen = 'flag camnearold\n' + scen
    d, man = PT.stage_full(C.OUT / 'scen', 'carcam' + ('_red' if negative else ''), scen, 5)
    if eboot: (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = Path(os.environ.get('SCEN_HOME', str(C.OUT / 'ppsspp_home'))); home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    # без /usr/bin/nice: защищённый системой бинарник срезает DYLD_FRAMEWORK_PATH, и эмулятор не находит SDL2 (03.10);
    # приоритет тот же — os.nice(10) в дочернем процессе
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen([str(PT.HEADLESS), '--graphics=software', '--timeout=300', str(d / 'EBOOT.PBP')], cwd=d, env=env,
                              stdout=log, stderr=subprocess.STDOUT, preexec_fn=lambda: os.nice(10))
        PT.watch_no_window(pr, 360)
    for b in sorted(d.glob('*.bmp')): PT.bmp_to_png(b, b.with_suffix('.png'))
    smoke = d / 'smoke.txt'; keep = d.parent / (d.name + '_log'); keep.mkdir(exist_ok=True)
    for f in [smoke, d / 'headless.log', *d.glob('*.png')]:   # журнал и снимки — рядом, клоны данных игры из папки прогона — прочь
        if f.exists(): shutil.copy2(f, keep / f.name)
    shutil.rmtree(d)
    print(f'прогон: {keep} (EBOOT {man.get("EBOOT.PBP") if not eboot else C.sha256(Path(eboot), 16)})')
    return keep / 'smoke.txt'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--eboot'); ap.add_argument('--negative', action='store_true'); ap.add_argument('--check')
    ap.add_argument('--expect-red', action='store_true')
    a = ap.parse_args()
    smoke = Path(a.check) if a.check else run(a.eboot, a.negative)
    return check(smoke, a.negative or a.expect_red)


if __name__ == '__main__':
    sys.exit(main())
