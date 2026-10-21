"""Правка Роба 263 (заменила 205): под заставкой GONE Makers музыки игры нет — только звук включения (кулер). Прогон короткого
сценария (меню сразу) в безоконном PPSSPP близнецов без звука; строка BOOTMUSIC (после заставки и лицензии) — не sunday_drive*.
python3 tests/bootsnd/music_run.py ИМЯ EBOOT.PBP -> 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P
SCN = 'flag menu\nwait 1.5\nend\n'

def run(name, eboot, timeout=150):
    out = C.OUT / 'bootmusic'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, SCN, 5)
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
    m = re.search(r'BOOTMUSIC music=(\S+)', s)
    ok = bool(m) and not m.group(1).startswith('sunday_drive')   # 263: темы уровня под заставкой нет
    print(f'{sys.argv[1]}: {"OK" if ok else "FAIL"} BOOTMUSIC music={m.group(1) if m else "нет строки"} ({d})'); sys.exit(0 if ok else 1)
