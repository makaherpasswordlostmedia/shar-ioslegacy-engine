#!/usr/bin/env python3
"""Правка Роба 362 (05.10: «поменять L/R — инверсию поставить, и добавить в настройках возможность менять L/R камеры»). Строка
оригинала «Invert Camera Control» в Settings паузы (PauseSettings.pag) включена: Off / On, по умолчанию On — поворот камеры пешком по
R/L наоборот прежнему (правка 75); значение — в settings.bin (Settings ver 4) и в записи сохранения (savegame.h ext[0]).
Безоконный PPSSPP без звука, сценарий tests/camera/camturn_scenario.txt: R 1 с -> Settings ► (Off) -> R 1 с -> Settings ► (On) -> R 1 с.
Поворот камеры — по строкам CAMF (курс камеры до и после нажатия), строки OPT экрана Settings (scr=2): строка не серая, inv.
КРАСНЫЙ: «flag camturnold 1» — R крутит камеру всегда в прежнюю сторону (настройка не действует). ЗЕЛЁНЫЙ: R по умолчанию — против
прежнего направления, после ► Off — как прежнее, после ► On — снова против; строка Invert включена; settings.bin рядом с EBOOT — ver 4,
invertCam = 1 (последнее значение).
    python3 tests/camera/camturn.py [EBOOT] [--parse]  -> 0 = PASS (SCEN_HOME, CAMTURN_TAG)"""
import math, os, re, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
TAG = os.environ.get('CAMTURN_TAG', 'camturn')


def start(name, eboot, old):
    txt = (['flag camturnold 1'] if old else []) + (ROOT / 'tests/camera/camturn_scenario.txt').read_text().splitlines()
    f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); f.write('\n'.join(txt) + '\n'); f.close()
    env = dict(os.environ, SCEN_EBOOT=str(eboot))
    if os.environ.get('SCEN_HOME'): env['SCEN_HOME'] = os.environ['SCEN_HOME'] + '/' + name
    return subprocess.Popen([sys.executable, str(SCEN), name, f.name], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def judge(name):
    d = OUT / name; p = d / 'smoke.txt'
    if not p.exists(): return None
    lines = p.read_text(errors='replace').splitlines()
    cam, presses, opt = [], [], []
    for l in lines:
        m = re.match(r'CAMF t=([\d.]+) st=(-?\d+) .*eye=([-\d.]+),([-\d.]+),([-\d.]+) look=([-\d.]+),([-\d.]+),([-\d.]+)', l)
        if m: v = [float(x) for x in m.groups()]; cam.append((v[0], math.atan2(v[5] - v[2], v[7] - v[4])))
        elif l.startswith('PRESS r '): presses.append(float(l.split()[2]))
        elif l.startswith('OPT ') and ' scr=2 ' in l: opt.append(dict(kv.split('=', 1) for kv in l.split()[1:] if '=' in kv))
    turns = []
    for t in presses:
        a = [y for tt, y in cam if t - .3 <= tt <= t]; b = [y for tt, y in cam if t + 1.0 <= tt <= t + 1.25]
        if a and b: turns.append(math.degrees((b[-1] - a[-1] + math.pi) % (2 * math.pi) - math.pi))
    rows = opt[0]['rows'].split(',') if opt else []
    st = None
    if (d / 'settings.bin').exists():
        b = (d / 'settings.bin').read_bytes()
        if len(b) >= 48 and b[:4] == b'SHST': st = struct.unpack_from('<i', b, 4)[0], struct.unpack_from('<i', b, 44)[0]
    return dict(turns=turns, row=rows[2] if len(rows) > 2 else None, inv=[o.get('inv') for o in opt], settings=st)


def main():
    eb = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    if '--parse' not in sys.argv:
        pr = [start(f'{TAG}_red', eb, True), start(f'{TAG}_green', eb, False)]
        for p in pr: p.wait(timeout=900)
    r, g = judge(f'{TAG}_red'), judge(f'{TAG}_green')
    if not r or not g: print('FAIL: нет прогона'); return 1
    fmt = lambda t: ', '.join(f'{x:+.0f}°' for x in t['turns'])
    print(f'красный (camturnold): повороты камеры по R {fmt(r)}')
    print(f'зелёный: повороты по R {fmt(g)}; строка Invert {g["row"]} (x — серая), inv по экранам {g["inv"]}; settings.bin (ver, invertCam) {g["settings"]}')
    fails = []
    if len(r['turns']) < 3 or len(g['turns']) < 3: fails.append('поворотов меньше 3 (сценарий не дошёл)')
    else:
        old = r['turns'][0]
        if abs(old) < 30 or any(math.copysign(1, x) != math.copysign(1, old) or abs(x) < 30 for x in r['turns']): fails.append('красный: прежнее направление не ровное')
        want = [-1, 1, -1]
        for i, (x, w) in enumerate(zip(g['turns'], want)):
            if abs(x) < 30 or math.copysign(1, x) != w * math.copysign(1, old): fails.append(f'поворот {i + 1}: {x:+.0f}° (ждём {"против" if w < 0 else "как"} прежнего {old:+.0f}°)')
    if g['row'] is None or g['row'].endswith('x'): fails.append(f'строка Invert Camera Control серая или нет ({g["row"]})')
    if g['settings'] != (4, 1): fails.append(f'settings.bin: {g["settings"]} (ждём ver 4, invertCam 1)')
    print('FAIL: ' + '; '.join(fails) if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
