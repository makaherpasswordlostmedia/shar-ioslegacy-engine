#!/usr/bin/env python3
"""Правка Роба 333 (05.10: «купил у Барни Plow King — Гомер садится с анимацией, как в низкую машину; в оригинале — круг к центру и
от центра»). Признак оригинала — SetIrisTransition(1) в scripts/cars/<машина>.con (viewer/carparams.h carIrisCons, car.c carIrisFor).
Запись PS2 yt-bziOipI4gDI: Plow King — посадка 869,25 с, выход 1085,20 с; ракетная 1978,45 с; угон седана трафика 2061,23 с — ирис
сразу, закрытие ~0,3 с, темно ~0,17 с, раскрытие ~0,3 с (темп ключей iris.p3d); famil_v без признака — клипы посадки (111 с).

Безоконный PPSSPP без звука, машина Plow King на месте своей (служебный «flag phonecar_plowk_v», как из будки), Гомер в 2 м слева:
  зелёный (plow):  △ -> IRIS why=car_in в первые 0,5 с, закрытие 14–30 кадров, темно+раскрытие 0,3–0,7 с, Гомер за рулём без
                   состояния HS_GET_IN (5), камера после ириса сразу своя (нет CAMBLEND в 1 с); снимок plow_a — экран чёрный, plow_b —
                   центр открыт, углы чёрные; △ ещё раз -> IRIS why=car_out, пешком без HS_GET_OUT (7)
  famil (зелёный): своя famil_v — как раньше: ириса car_* нет, посадка HS_GET_IN, выход HS_GET_OUT
  КРАСНЫЙ (plowred): «flag caririsold 1» — прежнее (клипы двери и у Plow King), сверка plow обязана упасть
python3 tests/homer/iris_car.py [EBOOT] -> 0 = PASS"""
import os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'

TAIL = ['wait 1.5', 'flag homerv', 'shot {n}_before', 'press triangle', 'wait 0.05', 'shot {n}_a', 'wait 0.1', 'shot {n}_b',
        'wait 0.45', 'flag homerv', 'wait 1.0', 'flag homerv', 'wait 1.5', 'flag homerv', 'shot {n}_incar', 'wait 1',
        'press triangle', 'wait 0.05', 'shot {n}_out_a', 'wait 0.45', 'flag homerv', 'wait 1.5', 'flag homerv', 'shot {n}_onfoot',
        'wait 0.5', 'end']

def scen(n):
    head = ['scene ' + n, 'flag msn', 'flag camlog', 'wait 3'] + (['flag caririsold 1'] if n.endswith('red') else []) + \
           ['goto 184.3 209.9 1.5708', 'wait 2']
    head += (['flag phonecar_plowk_v', 'wait 1.5', 'foot 184.3 206.6 0'] if n.startswith('ic_plow') else ['wait 1.5', 'foot 184.3 207.2 0'])
    return '\n'.join(head + [l.format(n=n) for l in TAIL]) + '\n'

def run(n, eboot):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f: f.write(scen(n)); sp = f.name
    home = Path(os.environ['SCEN_HOME']) / n if os.environ.get('SCEN_HOME') else Path(tempfile.mkdtemp(prefix='ic_home_'))
    env = dict(os.environ, SCEN_EBOOT=str(eboot), SCEN_HOME=str(home))
    subprocess.run([sys.executable, str(SCEN), n, sp], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    p = OUT / n / 'smoke.txt'
    return p.read_text(errors='replace') if p.exists() else ''

def kv(l): return dict(x.split('=', 1) for x in l.split() if '=' in x)

def presses(txt): return [float(m.group(1)) for m in re.finditer(r'^PRESS triangle ([\d.]+)', txt, re.M)]

def states(txt, a, b):   # состояния Гомера (flag homerv) на отрезке времени [a, b)
    return [int(kv(l)['state']) for l in txt.splitlines() if l.startswith('HOMERV ') and a <= float(kv(l)['t']) < b]

def black(n, name):
    p = OUT / n / f'{n}_{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('L')).astype(int); h, w = a.shape
    return (a < 12).mean(), (a[h // 2 - 10:h // 2 + 10, w // 2 - 10:w // 2 + 10] < 12).mean(), (a[:20, :20] < 12).mean()

def judge_plow(n, txt):
    if not re.search(r'^PHONECAR plowk_v ok=1 iris=1', txt, re.M): return 'Plow King не подставлен (нет PHONECAR plowk_v ok=1 iris=1)'
    pr = presses(txt)
    if len(pr) < 2: return 'нет двух нажатий △'
    L = txt.splitlines(); iris = [kv(l) | {'line': l} for l in L if l.startswith('IRIS ')]
    cin = [d for d in iris if d['why'] == 'car_in']
    if not cin or not cin[0]['line'].startswith('IRIS why=car_in phase=close f=0.00') or float(cin[0]['t']) - pr[0] > .5:
        return 'посадка не ирисом сразу (нет IRIS why=car_in phase=close в 0,5 с после △)'
    nclose = sum(1 for d in cin if d['phase'] == 'close')
    hold = [float(d['t']) for d in cin if d['phase'] == 'hold']; done = [float(d['t']) for d in cin if d['phase'] == 'done']
    if not (14 <= nclose <= 30): return f'темп закрытия не данных: {nclose} кадров (ждали 14–30; ×1,95 — ~40)'
    if not hold or not done or not (.3 <= done[0] - hold[0] <= .7): return f'темно+раскрытие не 0,3–0,7 с ({hold[:1]}, {done[:1]})'
    st = states(txt, pr[0], pr[1])
    if 5 in st or 6 not in st: return f'посадка: состояния {st} (ждали 6 без 5 — без клипов двери)'
    cb = [float(kv(l)['t']) for l in L if l.startswith('CAMBLEND ')]
    if any(pr[0] <= t < pr[0] + 1.0 for t in cb): return 'после ириса посадки камера ещё переходит (CAMBLEND) — должна быть сразу своя'
    cout = [d for d in iris if d['why'] == 'car_out']
    if not cout or float(cout[0]['t']) - pr[1] > .5: return 'выход не ирисом сразу (нет IRIS why=car_out в 0,5 с после △)'
    st2 = states(txt, pr[1], 1e9)
    if 7 in st2 or 0 not in st2: return f'выход: состояния {st2} (ждали 0 без 7)'
    a, b, oa = black(n, 'a'), black(n, 'b'), black(n, 'out_a')
    if not a or a[0] < .9: return f'снимок {n}_a: ирис не закрыт ({a})'
    if not b or b[1] > .1 or b[2] < .9: return f'снимок {n}_b: ирис не раскрывается из центра ({b})'
    if not oa or oa[0] < .9: return f'снимок {n}_out_a: ирис выхода не закрыт ({oa})'
    return ''

def judge_famil(txt):
    pr = presses(txt)
    if len(pr) < 2: return 'нет двух нажатий △'
    if re.search(r'^IRIS why=car_', txt, re.M): return 'у famil_v ирис car_* (признака SetIrisTransition у неё нет)'
    st, st2 = states(txt, pr[0], pr[1]), states(txt, pr[1], 1e9)
    if 5 not in st or 6 not in st: return f'посадка famil_v не клипами: состояния {st} (ждали 5, потом 6)'
    if 7 not in st2: return f'выход famil_v не клипами: состояния {st2} (ждали 7)'
    return ''

if __name__ == '__main__':
    eb = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    names = ['ic_plow', 'ic_plowred', 'ic_famil']
    with ThreadPoolExecutor(3) as ex: txt = dict(zip(names, ex.map(lambda n: run(n, eb), names)))
    green, red, fam = judge_plow('ic_plow', txt['ic_plow']), judge_plow('ic_plowred', txt['ic_plowred']), judge_famil(txt['ic_famil'])
    print(f'красный (flag caririsold 1): {red or "прошёл — проверка слепая"}')
    print(f'зелёный Plow King: {green or "OK — посадка и выход ирисом сразу, темп данных, без клипов двери, камера машины сразу"}')
    print(f'famil_v: {fam or "OK — как раньше, клипы посадки и выхода, без ириса"}')
    print('снимки:', OUT / 'ic_plow')
    ok = bool(red) and not green and not fam
    print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
