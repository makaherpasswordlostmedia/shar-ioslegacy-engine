"""Правка Роба 306 (04.10: «в m2 Барни и лавка, и собеседник миссии — подхожу поговорить по миссии, а он только лавка»): этап
m2 «TALK TO BARNEY»; Гомер в 2 м от Барни (внутри места лавки 2,5 м и разговора 4 м), △ — начинается разговор (этап m2.1.4
dialogue), экран лавки не открывается. Безоконный PPSSPP без звука. КРАСНЫЙ: «flag shopfirstold 1» — лавка перехватывает △.
python3 tests/npc/seller_talk.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['flag msn', 'wait 2'] + (['flag shopfirstold 1'] if old else []) +
                     ['flag msnmain 2', 'wait 3', 'press cross', 'wait 2', 'press cross', 'wait 2'] + ['flag msngo', 'wait 3'] * 3 +
                     ['flag sellerlog', 'foot 324.3 -129.4 3.1416', 'wait 1.5', 'flag sellerlog', 'press triangle', 'wait 3', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=500)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    if 'obj=talkto text="TALK TO BARNEY"' not in txt: return 'этап TALK TO BARNEY не начался'
    after = txt.split('PRESS triangle', 1)[-1] if 'PRESS triangle' in txt else ''
    if not after: return 'нет нажатия'
    if re.search(r'^SHOPV ', after, re.M): return 'открылась лавка'
    if not re.search(r'MSN stage m2\.1\.4 obj=dialogue', after): return 'разговор не начался'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('sellertalk_red', eb, True)); green = judge(run('sellertalk_green', eb, False))
    print(f'красный (flag shopfirstold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — разговор, не лавка"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
