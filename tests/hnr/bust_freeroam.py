"""Правка Роба 227: прогон tests/hnr/bust_freeroam.txt в безоконном PPSSPP близнецов (без звука), разбор журнала:
есть арест (HNR busted), нет провала миссии (MSN failed), есть строка «штраф без провала». python3 ... ИМЯ EBOOT -> 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P

def run(name, eboot, timeout=180):
    out = C.OUT / 'bust_freeroam'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, (ROOT / 'tests/hnr/bust_freeroam.txt').read_text(), 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    return d

if __name__ == '__main__':
    d = run(sys.argv[1], sys.argv[2]); s = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    busted, failed, fine = 'HNR busted' in s, re.search(r'MSN failed', s) is not None, 'fine-only' in s
    err = '' if busted and not failed and fine else f'арест={busted} провал миссии={failed} штраф без провала={fine}'
    print(f'{sys.argv[1]}: {"OK" if not err else "FAIL: " + err} ({d})'); sys.exit(1 if err else 0)
