"""Правка Роба 290 (04.10: «Гомер проходит через почтовые ящики и гидранты»): Гомер у спавна идёт ↑ 2 с курсом +x прямо на проп
уровня (PRP1 №459 у (219,5; 168,5), коробка 0,42 × 0,69 × 0,46) — должен упереться или обойти боком, а не пройти насквозь
(после ходьбы за пропом Гомер сдвинут вбок ≥ 0,5 м). Безоконный PPSSPP без звука. КРАСНЫЙ: «flag propsoftold 1» (пропы насквозь, как было) — обязан упасть.
python3 tests/homer/props_solid.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
PX, HALF = 219.5, 0.42

def scen(old):
    return '\n'.join(['flag player', 'scene foot'] + (['flag propsoftold 1'] if old else []) +
                     ['foot 216.5 168.51 1.5708', 'wait 2', 'press up 2.2', 'wait 2.4', 'flag homerv', 'wait 0.5', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):   # упёрся (x до коробки) или обошёл боком (z сдвинут на полкоробки + радиус Гомера); прямо сквозь — провал
    pts = [(float(x), float(z)) for x, z in re.findall(r'HOMER t=[\d.]+ pos=([-\d.]+),[-\d.]+,([-\d.]+)', txt)]
    if len(pts) < 3: return 'нет строк HOMER'
    x, z = pts[-1]
    if x < 217.3: return f'Гомер не пошёл (x {x:.2f})'
    if x >= PX - HALF and abs(z - 168.51) < 0.5: return f'прошёл сквозь проп: x {x:.2f}, сдвиг вбок {abs(z - 168.51):.2f} м'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('propsolid_red', eb, True)); green = judge(run('propsolid_green', eb, False))
    print(f'красный (flag propsoftold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — упёрся в проп"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
