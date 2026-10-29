"""Правка Роба 239: прогон сценария выхода в меню в безоконном PPSSPP (близнец tools/twins, звук не выводится) и проверка
журнала: после PAUSEACT act=7 строка FEBACK mode=0 (набор шин Normal) и последняя музыка — simpsons_theme.
python3 tests/fe_music/quit_run.py ИМЯ EBOOT.PBP  -> код 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P

def run(name, eboot, timeout=300):
    out = C.OUT / 'fe_quit'; out.mkdir(parents=True, exist_ok=True)
    scn = (ROOT / 'tests' / 'fe_music' / 'quit_scenario.txt').read_text()
    d, man = P.stage_full(out, name, scn, 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    return d

def check(smoke):
    s = Path(smoke).read_text(errors='replace') if Path(smoke).exists() else ''
    q = s.find('PAUSEACT act=7')
    if q < 0: return 'нет выхода из паузы (PAUSEACT act=7)'
    tail = s[q:]
    m = re.search(r'FEBACK mode=(\d+) state=(\d+)', tail)
    if not m: return 'нет строки FEBACK после выхода'
    mus = re.findall(r'STREAM s=music track=(\S+)', tail)
    if m.group(1) != '0': return f'в меню набор шин {m.group(1)} (1 = Pause: музыка и эффекты 0), не Normal'
    if not mus or mus[-1] != 'simpsons_theme': return f'последняя музыка после выхода {mus[-1] if mus else "-"}, не simpsons_theme'
    return ''

if __name__ == '__main__':
    d = run(sys.argv[1], sys.argv[2])
    err = check(d / 'smoke.txt')
    print(f'{sys.argv[1]}: {"OK" if not err else "FAIL: " + err} ({d})')
    sys.exit(1 if err else 0)
