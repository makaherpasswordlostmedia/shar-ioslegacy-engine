"""Правка Роба 267 (04.10: «в пузырях снизу текст обрублен; когда взрывается машина, текст громадный, еле вмещается»): сообщение
«VEHICLE DESTROYED! …» в нижнем пузыре без значка — переносится по ширине пузыря (не 4 жёсткие строки); с правки 295 блок от верха пузыря.
 Снимок через 4 с после взрыва (flag testboom). КРАСНЫЙ: «flag msghardbr 1» — 4 строки.
python3 tests/ui/bubble_reflow.py [EBOOT] -> 0 = PASS"""
import os, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = ROOT / 'build/twins/scen/full'; OUT = ROOT / 'build/gates/bubble267'
BASE = ['flag msn', 'wait 2', 'goto 220 172 1.5708', 'wait 1', 'flag testboom', 'wait 6', 'shot b', 'end']

def run(name, eboot, red):
    OUT.mkdir(parents=True, exist_ok=True); p = OUT / f'{name}.txt'
    p.write_text('\n'.join([f'scene {name}'] + (['flag msghardbr 1'] if red else []) + BASE) + '\n')
    subprocess.run([sys.executable, str(SCEN), name, str(p)], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(OUT / 'home')), capture_output=True, timeout=600)
    return RUNS / name / 'b.png'

def rows(png):   # строки жёлтого текста в нижнем пузыре (x 55..300, y 185..235, ниже верхней кромки рамки y 183): число строк, поля сверху/снизу до краёв пузыря
    a = np.asarray(Image.open(png).convert("RGB"), int)[185:236, 55:300]
    yel = (a[..., 0] > 200) & (a[..., 1] > 180) & (a[..., 2] < 120)
    ink = yel.sum(1) > 20; ys = np.where(ink)[0]   # строка текста — десятки жёлтых точек; рамка пузыря сбоку — 2–6 (правка 295: текст у верха, рамка рядом)
    if not len(ys): return 0, None
    lines = 1 + int(sum(1 for i in range(1, len(ys)) if ys[i] - ys[i - 1] > 2))
    return lines, (int(ys[0]), int(ys[-1]))

if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    rl, _ = rows(run('bub_red', eb, True)); gl, gy = rows(run('bub_green', eb, False))
    print(f'красный (msghardbr): строк {rl}; зелёный: строк {gl}, текст по строкам {gy}')
    ok = rl >= 4 and 1 <= gl <= 3
    print('PASS: перенос по ширине пузыря, красный пойман' if ok else 'FAIL'); sys.exit(0 if ok else 1)
