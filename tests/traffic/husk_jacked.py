"""Правка Роба 286 (04.10: «школьный автобус горит и взрывается, но стоит целый»): угнанный школьный автобус разбит (flag testboom)
— после взрыва на его месте остов (huskA), а не целый автобус: строка PLAYERHUSK car=schoolbu husk=1, снимок boom.png.
КРАСНЫЙ: «flag huskold 1» — прежнее (целая модель), обязан упасть. python3 tests/traffic/husk_jacked.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['wait 3', 'flag msn', 'wait 3'] + (['flag huskold 1'] if old else []) +
                     ['scene schoolbu', 'foot 298.0 179.5 -1.5708', 'wait 2', 'press triangle', 'wait 4', 'flag testboom', 'wait 7',
                      'shot boom', 'wait 1', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=400)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    if 'CARJACK model=schoolbu' not in txt: return 'автобус не угнан'
    m = re.search(r'PLAYERHUSK car=(\S+) husk=(\d)', txt)
    if not m: return 'взрыв не дошёл до рисования'
    return '' if m.group(1) == 'schoolbu' and m.group(2) == '1' else f'после взрыва целая модель ({m.group(0)})'

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('husk_red', eb, True)); green = judge(run('husk_green', eb, False))
    print(f'красный (flag huskold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — остов на месте автобуса"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
