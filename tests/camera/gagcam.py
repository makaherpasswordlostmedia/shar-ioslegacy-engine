#!/usr/bin/env python3
"""Правка Роба 338 (05.10: «у уникальных мест — гэгов (пример L1 H4-7) — кривые ракурсы»). Газ у АЭС: у кнопки снимает камера зоны
r6_cam с диска (l1r6.p3d: низко, FOV 75, цель на 5 м над Гомером). Было: вход и выход — срезом (глаз прыгал на 8–16 м за кадр).
Правило порта по данным (main.c, толкование CutInOut / TransitionTargetRate статичной камеры): камеры зон с CutInOut 0 — плавным
переходом (строка ZONEBLEND). Безоконный PPSSPP без звука, сценарий tests/camera/gagcam_scenario.txt.
КРАСНЫЙ: «flag zonecutold 1» — переходов нет, скачок глаза на смене камеры > 3 м. ЗЕЛЁНЫЙ: переходы на каждой смене (вход и выход),
скачок глаза на смене камеры < 1,5 м, камера игры ни разу не внутри (CAMIN any 0).
    python3 tests/camera/gagcam.py [EBOOT]  -> 0 = PASS (SCEN_HOME — свой HOME эмулятора)"""
import math, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
TAG = os.environ.get('GAGCAM_TAG', 'gagcam')


def start(name, eboot, old):
    txt = (['flag zonecutold 1'] if old else []) + (ROOT / 'tests/camera/gagcam_scenario.txt').read_text().splitlines()
    f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); f.write('\n'.join(txt) + '\n'); f.close()
    env = dict(os.environ, SCEN_EBOOT=str(eboot))
    if os.environ.get('SCEN_HOME'): env['SCEN_HOME'] = os.environ['SCEN_HOME'] + '/' + name
    return subprocess.Popen([sys.executable, str(SCEN), name, f.name], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def judge(name):
    p = OUT / name / 'smoke.txt'
    if not p.exists(): return None
    rows, zsw, blends, cam = [], [], 0, {}
    for l in p.read_text(errors='replace').splitlines():
        if l.startswith('CAMF '):
            m = re.search(r't=([\d.]+) .*eye=([-\d.]+),([-\d.]+),([-\d.]+) look', l)
            if m: rows.append([float(v) for v in m.groups()])
        elif l.startswith('ZONECAM t='): zsw.append(float(re.search(r't=([\d.]+)', l).group(1)))
        elif l.startswith('ZONEBLEND'): blends += 1
        elif l.startswith('CAMIN t='): cam = dict(kv.split('=', 1) for kv in l.split()[1:] if '=' in kv)
    jumps = []
    for t in zsw[1:]:   # первая смена — перенос сценарием
        win = [r for r in rows if t - .05 <= r[0] <= t + .6]
        jumps.append(max((math.dist(a[1:], b[1:]) for a, b in zip(win, win[1:])), default=0.))
    return dict(switches=len(zsw) - 1, blends=blends, jump=max(jumps, default=0.), occ=int(cam.get('occ', -1)), inside=int(cam.get('any', -1)),
                frames=int(cam.get('frames', 0)))


def main():
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    pr = [start(f'{TAG}_red', eb, True), start(f'{TAG}_green', eb, False)]
    for p in pr: p.wait(timeout=900)
    r, g = judge(f'{TAG}_red'), judge(f'{TAG}_green')
    if not r or not g: print('FAIL: нет прогона'); return 1
    print(f'красный: смен камеры {r["switches"]}, переходов {r["blends"]}, скачок глаза на смене {r["jump"]:.2f} м, внутри {r["inside"]}')
    print(f'зелёный: смен камеры {g["switches"]}, переходов {g["blends"]}, скачок глаза на смене {g["jump"]:.2f} м, внутри {g["inside"]} (кадров {g["frames"]})')
    fails = []
    if r['switches'] < 2: fails.append('сценарий: Гомер не выходил из триггера r6_cam')
    if not (r['jump'] > 3. and r['blends'] == 0): fails.append('красный контроль не пойман (прежнее не срезом)')
    if g['blends'] < g['switches']: fails.append(f'переходов {g["blends"]} на {g["switches"]} смен камеры')
    if g['jump'] >= 1.5: fails.append(f'скачок глаза на смене камеры {g["jump"]:.2f} м')
    if g['inside'] != 0: fails.append(f'камера внутри в {g["inside"]} кадрах')
    print('FAIL: ' + '; '.join(fails) if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
