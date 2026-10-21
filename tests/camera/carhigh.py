#!/usr/bin/env python3
"""Правка Роба 360 (05.10: «камеру капельку выше: всё прямо за машиной, не видно центр дороги, куда едем»). Сверка с оригиналом
(knowledge/facts/ps2-camera-fov.yaml, близнец v28_drive_cam: в езде глаз 3,3–3,6 м над началом машины, взгляд вниз ~15°): прежняя камера
L1 — 3,43 м и 14,1–14,5° — уже как оригинал, поэтому один небольшой шаг выше: высота глаза над началом модели × CAM_EYE_K (1,10).
Безоконный PPSSPP без звука, сценарий tests/camera/carcam_scenario.txt (famil_v, школьный автобус; стоя и в езде), строки CARCAM.
КРАСНЫЙ: «flag camhighold 1» — прежняя высота: famil_v взгляд вниз 15° ± 1,2 (как PS2). ЗЕЛЁНЫЙ: глаз famil_v выше на 0,25–0,45 м,
взгляд круче на 1–2,5°, горизонт на кадре выше на 4–12 px из 272; у автобуса тоже выше; доля экрана под кузовом famil_v — в пределах
±15 % от PS2 (как гейт carcam_ps2).
    python3 tests/camera/carhigh.py [EBOOT] [--parse]  -> 0 = PASS (SCEN_HOME, CARHIGH_TAG)"""
import math, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
TAG = os.environ.get('CARHIGH_TAG', 'carhigh')
PS2_PITCH = 15.1   # fwd.y −0,26 (ps2-camera-fov.yaml, в езде ~16 м/с)


def start(name, eboot, old):
    txt = (['flag camhighold 1'] if old else []) + (ROOT / 'tests/camera/carcam_scenario.txt').read_text().splitlines()
    f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); f.write('\n'.join(txt) + '\n'); f.close()
    env = dict(os.environ, SCEN_EBOOT=str(eboot))
    if os.environ.get('SCEN_HOME'): env['SCEN_HOME'] = os.environ['SCEN_HOME'] + '/' + name
    return subprocess.Popen([sys.executable, str(SCEN), name, f.name], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def judge(name):
    p = OUT / name / 'smoke.txt'
    if not p.exists(): return {}
    res = {}
    for l in p.read_text(errors='replace').splitlines():
        if not l.startswith('CARCAM '): continue
        kv = dict(x.split('=', 1) for x in l.split()[1:] if '=' in x)
        if kv.get('ps2') != '1' or float(kv['wall']) < .999: continue
        e = [float(x) for x in kv['eye'].split(',')]; k = [float(x) for x in kv['look'].split(',')]; pos = [float(x) for x in kv['pos'].split(',')]
        f = [k[i] - e[i] for i in range(3)]; L = math.sqrt(sum(x * x for x in f))
        pitch = math.degrees(math.asin(-f[1] / L)); tv = math.tan(math.radians(float(kv['fovy']) / 2))
        hor = 136 - 136 * math.tan(math.radians(pitch)) / tv   # строка горизонта на кадре 272 (сверху)
        mode = 'drive' if abs(float(kv['v'])) > 5 else 'still'
        res.setdefault((kv['car'], mode), []).append((pitch, e[1] - pos[1] - float(kv['lift']), hor))
    return {key: tuple(sum(v[i] for v in vals) / len(vals) for i in range(3)) for key, vals in res.items()}


def main():
    eb = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    if '--parse' not in sys.argv:
        for old, name in ((True, f'{TAG}_red'), (False, f'{TAG}_green')):
            start(name, eb, old).wait(timeout=900)
    r, g = judge(f'{TAG}_red'), judge(f'{TAG}_green')
    fails = []
    for key in sorted(set(r) & set(g)):
        a, b = r[key], g[key]
        print(f'{key[0]:8s} {key[1]:5s}: взгляд вниз {a[0]:.1f}° -> {b[0]:.1f}°, глаз над началом модели {a[1]:.2f} -> {b[1]:.2f} м, горизонт {a[2]:.0f} -> {b[2]:.0f} px')
        if key[0] == 'famil_v':
            if key[1] == 'drive' and abs(a[0] - PS2_PITCH) > 1.2: fails.append(f'красный famil_v в езде {a[0]:.1f}° — не как PS2 ({PS2_PITCH}°)')
            if not (.25 <= b[1] - a[1] <= .45): fails.append(f'famil_v {key[1]}: глаз выше на {b[1] - a[1]:.2f} м')
            if not (1. <= b[0] - a[0] <= 2.5): fails.append(f'famil_v {key[1]}: взгляд круче на {b[0] - a[0]:.1f}°')
            if not (4 <= a[2] - b[2] <= 12): fails.append(f'famil_v {key[1]}: горизонт выше на {a[2] - b[2]:.0f} px')
        elif b[1] <= a[1]: fails.append(f'{key}: глаз не выше')
    if ('famil_v', 'still') not in g or ('famil_v', 'drive') not in g: fails.append('нет кадров famil_v')
    out = subprocess.run([sys.executable, str(ROOT / 'tests/camera/carcam_ps2.py'), '--check', str(OUT / f'{TAG}_green' / 'smoke.txt')], capture_output=True, text=True).stdout
    for l in out.splitlines():
        if l.startswith('famil_v') or l.startswith('schoolbu'): print('  carcam_ps2: ' + l.strip()[:150])
    if 'famil_v: доля экрана' in out: fails.append('carcam_ps2: доля экрана famil_v вне ±15 % от PS2')
    print('FAIL: ' + '; '.join(fails) if fails else 'PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
