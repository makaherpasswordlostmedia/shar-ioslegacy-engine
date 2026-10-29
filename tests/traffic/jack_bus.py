"""Правка Роба 285 (04.10: «подхожу к школьному автобусу, пытаюсь сесть — он тупит»): Гомер у борта стоящего школьного автобуса
(Z1PC, 295,5; 177,4), ближе к корме — 2,5 м вдоль и 2,1 м вбок от центра: до кузова 0,9 м, до центра минус полуширина 2 м.
△ — угон и посадка под ирисом сразу (CARJACK model=schoolbu, IRIS why=seat в ту же секунду). Безоконный PPSSPP без звука.
КРАСНЫЙ: «flag trfnearold 1» (прежняя мера: центр − полуширина) — автобус не находится, гейт обязан упасть.
python3 tests/traffic/jack_bus.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['wait 3', 'flag msn', 'wait 3'] + (['flag trfnearold 1'] if old else []) +
                     ['scene schoolbu', 'foot 298.0 179.5 -1.5708', 'wait 2', 'press triangle', 'wait 3', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=400)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    tri = re.search(r'PRESS triangle ([\d.]+)', txt)
    if not tri: return 'нет нажатия'
    j = re.search(r'CARJACK model=schoolbu .*t=([\d.]+)', txt)
    if not j: return 'автобус не угнан (%s)' % (re.search(r'TRIJACK [^\n]*', txt) or [''])[0]
    ir = re.search(r'IRIS why=(?:seat|car_in) phase=close f=0\.00 .*t=([\d.]+)', txt)   # 333: schoolbu — SetIrisTransition, ирис car_in
    if not ir or float(ir.group(1)) - float(tri.group(1)) > 0.5: return 'посадка не под ирисом сразу'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('jackbus_red', eb, True)); green = judge(run('jackbus_green', eb, False))
    print(f'красный (flag trfnearold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — автобус угнан, сразу ирис"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
