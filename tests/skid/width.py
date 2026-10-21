"""Правка Роба 270 (04.10: «следы — очень широкие, в оригинале тоньше»): ширина следа к расстоянию между двумя следами на снимке
skid_after сценария tests/skid/scenario.txt — как на записи PS2 2:50 (30/195 = 0,15; допуск 0,10–0,20). Безголовый эмулятор.
КРАСНЫЙ: «flag skidwide 1» (прежние 0,5 м, отношение 0,27) обязан упасть. python3 tests/skid/width.py [EBOOT] -> 0 = PASS"""
import os, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = ROOT / 'build/twins/scen/full'; OUT = ROOT / 'build/gates/skidw'

def run(name, eboot, wide):
    OUT.mkdir(parents=True, exist_ok=True)
    sc = [l for l in (ROOT / 'tests/skid/scenario.txt').read_text().splitlines() if not l.startswith('#')]
    if wide: sc.insert(1, 'flag skidwide 1')
    p = OUT / f'{name}.txt'; p.write_text('\n'.join(sc) + '\n')
    subprocess.run([sys.executable, str(SCEN), name, str(p)], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(OUT / ('home_' + name))),
                   capture_output=True, timeout=600)
    return RUNS / name / 'skid_after.png'

def ratio(png):   # строки у низа кадра: два тёмных отрезка (след) на асфальте за машиной; -> медиана ширина/расстояние
    a = np.asarray(Image.open(png).convert('RGB'), float).mean(2); rs = []
    for y in range(240, 268, 2):
        row = a[y, 150:330]; base = np.median(row); dark = row < base * .75
        runs, x = [], 0
        while x < len(dark):
            if dark[x]:
                x0 = x
                while x < len(dark) and dark[x]: x += 1
                if x - x0 >= 3: runs.append((x0, x))
            x += 1
        if len(runs) >= 2:
            (a0, a1), (b0, b1) = runs[0], runs[-1]
            rs.append(((a1 - a0) + (b1 - b0)) / 2 / (((b0 + b1) - (a0 + a1)) / 2))
    return float(np.median(rs)) if rs else None

if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    r = ratio(run('skidw_red', eb, True)); g = ratio(run('skidw_green', eb, False))
    print(f'красный (flag skidwide): ширина/колея {r}'); print(f'зелёный: ширина/колея {g} (PS2 0,15)')
    ok = r is not None and g is not None and r > .22 and .10 <= g <= .20
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
