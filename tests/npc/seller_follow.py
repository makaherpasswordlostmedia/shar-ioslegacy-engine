"""Правка Роба 288 (04.10: «Барни ходит, но взаимодействуешь не с ним, а с местом на асфальте»): Барни (AddPurchaseCarReward
barney_loc, маршрут barney_walk1 — 8 м) дошёл до конца маршрута; Гомер в 1,5 м от самого Барни — подсказка «Shop» у △ есть
(место разговора идёт за продавцом). Безоконный PPSSPP без звука. КРАСНЫЙ: «flag selleratloc 1» — место на локаторе, у Барни
подсказки нет. python3 tests/npc/seller_follow.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['wait 3', 'flag msn'] + (['flag selleratloc 1'] if old else []) +
                     ['wait 28', 'flag sellerlog', 'foot 325.75 -131.74 -1.5708', 'wait 2.5', 'shot near', 'wait 0.5', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=400)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    m = re.search(r'SELLERNPC barney pos=([-\d.]+),[-\d.]+,([-\d.]+) walking=0', txt)
    if not m or abs(float(m.group(2)) + 131.74) > 0.8: return 'Барни не дошёл до конца маршрута (%s)' % (m.group(0) if m else '-')
    after = txt.split('FOOT ', 1)[-1]
    if not re.search(r'ACTTEXT Shop', after): return 'у самого Барни нет подсказки «Shop»'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('seller_red', eb, True)); green = judge(run('seller_green', eb, False))
    print(f'красный (flag selleratloc): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — у Барни подсказка Shop"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
