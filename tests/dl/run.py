"""Правка 275 (план ведущего 04.10 §2): дисплей-листы клеток города. Восемь видов уровня 1 в безоконном PPSSPP: листы против
прежнего пути по кускам («flag dloff»). Зелёный: на каждом виде отличается не больше 3 % пикселей (рисуются клетки целиком и туман
один на клетку — оттенок дальней листвы), процессор на подачу города (строка CITYDL) в среднем вдвое меньше прежнего, без
отказа сборки листа (fall 0 после первой секунды). КРАСНЫЙ: «flag dlnodepth 1» (лист без границ глубины — дома пропадают) обязан
упасть по картинке. python3 tests/dl/run.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
RUNS = ROOT / 'build/twins/scen/full'; OUT = ROOT / 'build/gates/dl'
VIEWS = ['220 172 1.5708', '214 300 3.1416', '-183 250 0', '-90 200 0', '100 -150 1.0', '350 -150 4.0', '300 450 2.5', '-250 -200 0.5']

def run(name, eboot, flag=None):
    OUT.mkdir(parents=True, exist_ok=True); sc = ['scene ' + name] + ([flag] if flag else [])
    for k, v in enumerate(VIEWS): sc += [f'goto {v}', 'wait 2', f'shot v{k}']
    p = OUT / f'{name}.txt'; p.write_text('\n'.join(sc + ['end']) + '\n')
    subprocess.run([sys.executable, str(SCEN), name, str(p)], env=dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(OUT / ('home_' + name))),
                   capture_output=True, timeout=900)
    d = RUNS / name; txt = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    ms = [float(x) for x in re.findall(r'CITYDL ms=([\d.]+)', txt)]; fall = [int(x) for x in re.findall(r'CITYDL .* fall=(\d+)', txt)]
    return d, ms, fall

def diff(a, b):
    out = []
    for k in range(len(VIEWS)):
        pa, pb = a / f'v{k}.png', b / f'v{k}.png'
        if not pa.exists() or not pb.exists(): out.append(1.0); continue
        x = np.asarray(Image.open(pa).convert('RGB'), int); y = np.asarray(Image.open(pb).convert('RGB'), int)
        out.append(float((np.abs(x - y).max(2) > 8).mean()))
    return out

if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    old, ms_old, _ = run('dlg_old', eb, 'flag dloff 1'); new, ms_new, fall = run('dlg_new', eb); red, _, _ = run('dlg_red', eb, 'flag dlnodepth 1')
    dn, dr = diff(new, old), diff(red, old)
    a, b = (np.mean(ms_old) if ms_old else 0), (np.mean(ms_new) if ms_new else 1e9)
    print('листы/прежний, доля отличных пикселей по видам:', ' '.join(f'{x * 100:.2f}%' for x in dn))
    print('красный (dlnodepth)/прежний:', ' '.join(f'{x * 100:.1f}%' for x in dr))
    print(f'подача города, мс процессора (эмулятор): прежний {a:.3f}, листы {b:.3f} (×{a / b if b else 0:.1f}); отказов сборки после 1 с: {sum(fall[1:])}')
    ok_new = max(dn) <= .03 and b * 2 <= a and sum(fall[1:]) == 0
    ok_red = max(dr) > .10
    print('PASS: листы как прежний путь, вдвое дешевле; красный пойман' if ok_new and ok_red else f'FAIL (зелёный {ok_new}, красный пойман {ok_red})')
    sys.exit(0 if ok_new and ok_red else 1)
