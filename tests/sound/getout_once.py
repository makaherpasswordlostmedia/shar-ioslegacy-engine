"""Правка Роба 303 (04.10: «после выхода из машины снова и снова мелодия: играет две секунды и начинается заново»): m2 (Petty Theft
Homer), Гомер в машине, △ — выход; событие M2_get_out_of_car ставит концовку gogo_end_sus один раз: через 8 с после выхода поток
музыки уже не она (строки AUDV cur=). Безоконный PPSSPP без звука. КРАСНЫЙ: «flag susloopold 1» — петля по данным (cur= всё ещё
gogo_end_sus). python3 tests/sound/getout_once.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'

def scen(old):
    return '\n'.join(['flag msn', 'wait 2'] + (['flag susloopold 1'] if old else []) +
                     ['flag msnmain 2', 'wait 3', 'press cross', 'wait 2', 'press cross', 'wait 2', 'flag msngo', 'wait 4',
                      'press triangle', 'wait 12', 'end']) + '\n'

def run(name, eboot, old):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(old)); sp = f.name
    subprocess.run([sys.executable, str(SCEN), name, sp], cwd=ROOT, env=dict(os.environ, SCEN_EBOOT=str(eboot)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=500)
    p = ROOT / 'build/twins/scen/full' / name / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def judge(txt):
    m = re.search(r'MUSIC event (M\d_get_out_of_car) -> (\S+)', txt)
    if not m: return 'нет события выхода из машины'
    ev, trk = m.groups()
    au = [(float(t), c) for t, c in re.findall(r'^AUDV t=([\d.]+) .*? cur=(\S+)', txt, re.M)]
    t0 = next((t for t, c in au if c == trk), None)
    if t0 is None: return f'концовка {trk} не заиграла'
    late = [c for t, c in au if t > t0 + 8]
    if not late: return 'нет строк AUDV через 8 с'
    if all(c == trk for c in late): return f'{trk} крутится петлёй ({len(late)} с после 8 с)'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    red = judge(run('getout_red', eb, True)); green = judge(run('getout_green', eb, False))
    print(f'красный (flag susloopold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — концовка один раз"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
