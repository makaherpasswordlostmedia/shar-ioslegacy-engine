"""Правка Роба 236: значок своей машины (группа PlayerCars радара оригинала) — пешком виден, в машине нет.
python3 tests/ui/radar_car.py ИМЯ EBOOT.PBP -> код 0 = PASS. Безоконный PPSSPP близнецов (tools/twins), без звука.
Проверка по значению: число нарисованных значков радара пешком у машины на 1 больше, чем в машине (строки RADAR drawn=),
и снимок: в круге радара есть пиксели значка (бирюза кузова) — в старой сборке их нет"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P
from PIL import Image

def run(name, eboot, timeout=240):
    out = C.OUT / 'radar_car'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, (ROOT / 'tests/ui/radar_car_scenario.txt').read_text(), 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    for b in sorted(d.glob('*.bmp')): P.bmp_to_png(b, b.with_suffix('.png'))
    return d

def teal(png):   # пиксели значка машины в круге радара (правый нижний угол): бирюза — G и B много больше R
    im = Image.open(png).convert('RGB'); w, h = im.size
    box = im.crop((int(w * .80), int(h * .62), w, h)); n = 0
    for r, g, b in box.getdata():
        if b > 150 and g > 150 and r < 110: n += 1
    return n

def check(d):
    s = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    rows = [(float(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4))) for m in
            re.finditer(r'RADAR t=([\d.]+) drawn=(\d+) .*? pos=([-\d.]+),([-\d.]+)', s)]
    if not rows: return 'нет строк RADAR'
    incar = [r for r in rows if abs(r[2] - 220.0) < 1.5 and abs(r[3] - 172.0) < 1.5 and r[0] < 2.5]
    near = [r for r in rows if abs(r[2] - 240.0) < .5 and abs(r[3] - 160.0) < .5]
    if not incar or not near: return f'нет строк в машине ({len(incar)}) или пешком у машины ({len(near)})'
    if near[-1][1] != incar[-1][1] + 1: return f'значков пешком {near[-1][1]}, в машине {incar[-1][1]}: машины на радаре нет'
    tn, tc = teal(d / 'radar_near.png'), teal(d / 'incar.png')
    if tn < 6 or tn <= tc: return f'на снимке радара пешком пикселей значка {tn} (в машине {tc}): значка не видно'
    return ''

if __name__ == '__main__':
    d = run(sys.argv[1], sys.argv[2]); err = check(d)
    print(f'{sys.argv[1]}: {"OK" if not err else "FAIL: " + err} ({d})'); sys.exit(1 if err else 0)
