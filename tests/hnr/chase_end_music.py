"""Правка Роба 266 (04.10: «погоня не заканчивается — музыка не заканчивается»): шкала 100 -> погоня (hit_run_intro), шкала спала
ниже 5 -> «HNR lost» и в тот же миг музыка места (не hit_run_*). Безоконный PPSSPP близнецов без звука.
КРАСНЫЙ: «flag hnrmusold 1» (прежний конец погони) обязан упасть. python3 tests/hnr/chase_end_music.py [EBOOT] -> 0 = PASS"""
import os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'twins'))
import common as C, port as P

def scen(old):
    return '\n'.join(['flag msn', 'wait 2'] + (['flag hnrmusold 1'] if old else []) +
                     ['goto 220 172 1.5708', 'wait 1', 'flag hnr 100', 'wait 1', 'press cross 5', 'wait 24', 'end']) + '\n'

def run(name, eboot, old, timeout=150):
    out = C.OUT / 'hnr_end'; out.mkdir(parents=True, exist_ok=True)
    d, man = P.stage_full(out, name, scen(old), 5)
    (d / 'EBOOT.PBP').unlink(); shutil.copy2(eboot, d / 'EBOOT.PBP')
    home = C.OUT / ('ppsspp_home_' + name); home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, timeout + 60)
    return (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''

def judge(txt):
    lost = re.search(r'HNR lost t=([\d.]+)', txt)
    if not re.search(r'HNR chase t=', txt) or not lost: return 'погоня не началась или не кончилась'
    tl = float(lost.group(1)); mus = [(float(t), tr) for tr, t in re.findall(r'STREAM s=music track=(\S+) .* t=([\d.]+)', txt)]
    last = [tr for t, tr in mus if t <= tl + 0.5]
    if not last or last[-1].startswith('hit_run'): return f'после конца погони ({tl:.1f} с) играет {last[-1] if last else "-"}'
    return ''

if __name__ == '__main__':
    eb = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'viewer/build/EBOOT.PBP')
    red = judge(run('red', eb, True)); green = judge(run('green', eb, False))
    print(f'красный (flag hnrmusold): {red or "прошёл — проверка слепая"}'); print(f'зелёный: {green or "OK — музыка места после погони"}')
    ok = bool(red) and not green
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
