#!/usr/bin/env python3
"""Правка Роба 361 (05.10: «вышли из машины, вылетели, машина взорвалась — камера преследует точку машины, показывает, где машина;
надо показывать по направлению движения героя»). Безоконный PPSSPP без звука, сценарий tests/camera/herocam_scenario.txt: машина
разбивается на ходу, после прыжка F10-5 и о стену (строка BOOM), Гомера выбрасывает, машина горит и взрывается. По строкам CAMF
(flag camlog) в окне 0,4–5 с после разбития, пока Гомер не в машине:
  к машине — средний угол между курсом камеры и направлением «Гомер -> машина»;
  к герою  — средний угол между курсом камеры и направлением движения Гомера (от места разбития, когда он ушёл дальше 1 м).
КРАСНЫЙ: «flag boomcamold 1» (правило 199: камера держит горящую машину; после выброса — по курсу машины) — хотя бы в 2 сценах камера на
машине (к машине < 40°) и не по движению героя (к герою > 60°). ЗЕЛЁНЫЙ: в каждой сцене к герою < 35° (машина может оказаться впереди
сама — если её несёт туда же, куда летит Гомер).
    python3 tests/camera/herocam.py [EBOOT] [--parse]  -> 0 = PASS (SCEN_HOME — свой HOME эмулятора, HEROCAM_TAG — имена прогонов)"""
import math, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
TAG = os.environ.get('HEROCAM_TAG', 'herocam')


def start(name, eboot, old):
    txt = (['flag boomcamold 1'] if old else []) + (ROOT / 'tests/camera/herocam_scenario.txt').read_text().splitlines()
    f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); f.write('\n'.join(txt) + '\n'); f.close()
    env = dict(os.environ, SCEN_EBOOT=str(eboot))
    if os.environ.get('SCEN_HOME'): env['SCEN_HOME'] = os.environ['SCEN_HOME'] + '/' + name
    return subprocess.Popen([sys.executable, str(SCEN), name, f.name], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def judge(name):
    p = OUT / name / 'smoke.txt'
    if not p.exists(): return {}
    scene, ej, rows, res = None, {}, {}, {}
    for l in p.read_text(errors='replace').splitlines():
        if l.startswith('SCENE '): scene = l.split()[1]
        elif l.startswith('BOOM ') and scene and scene not in ej:
            m = re.search(r't=([\d.]+)', l); ej[scene] = float(m.group(1))
        elif l.startswith('CAMF ') and scene:
            m = re.search(r't=([\d.]+) st=(-?\d+) .*eye=([-\d.]+),([-\d.]+),([-\d.]+) look=([-\d.]+),([-\d.]+),([-\d.]+) homer=([-\d.]+),([-\d.]+),([-\d.]+) car=([-\d.]+),([-\d.]+),([-\d.]+)', l)
            if m: rows.setdefault(scene, []).append([float(v) for v in m.groups()])
    for sc, t0 in ej.items():
        R = [r for r in rows.get(sc, []) if t0 + .4 <= r[0] <= t0 + 5. and int(r[1]) not in (6, 7)]   # Гомер не в машине
        R0 = [r for r in rows.get(sc, []) if r[0] >= t0]
        if not R or not R0: continue
        h0 = R0[0][8:11]; tocar, tohero, nh = [], [], 0
        for r in R:
            yaw = math.atan2(r[5] - r[2], r[7] - r[4])
            tocar.append(abs(wrap(yaw - math.atan2(r[11] - r[8], r[13] - r[10]))))
            dx, dz = r[8] - h0[0], r[10] - h0[2]
            if math.hypot(dx, dz) > 1.: tohero.append(abs(wrap(yaw - math.atan2(dx, dz)))); nh += 1
        res[sc] = dict(car=math.degrees(sum(tocar) / len(tocar)), hero=math.degrees(sum(tohero) / len(tohero)) if tohero else None, n=len(R))
    return res


def main():
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    if '--parse' not in sys.argv:   # --parse: только разбор снятых прогонов
        pr = [start(f'{TAG}_red', eb, True), start(f'{TAG}_green', eb, False)]
        for p in pr: p.wait(timeout=900)
    r, g = judge(f'{TAG}_red'), judge(f'{TAG}_green')
    fails, red_hits = [], 0
    for sc in sorted(set(r) | set(g)):
        a, b = r.get(sc), g.get(sc)
        f = lambda d, k: '—' if not d or d.get(k) is None else f'{d[k]:.0f}°'
        print(f'{sc}: красный к машине {f(a, "car")}, к герою {f(a, "hero")}  ->  зелёный к машине {f(b, "car")}, к герою {f(b, "hero")}')
        if a and a['car'] < 40. and a['hero'] is not None and a['hero'] > 60.: red_hits += 1
        if b and (b['hero'] is None or b['hero'] >= 35.): fails.append(f'{sc}: камера не по движению героя ({b})')
    if len(g) < 2: fails.append(f'выбросов в зелёном {len(g)} из 3 сцен (сценарий не дошёл)')
    if red_hits < 2: fails.append(f'красный контроль: камера на машине только в {red_hits} сценах')
    print('FAIL: ' + '; '.join(fails) if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
