#!/usr/bin/env python3
"""Правка 496: пятна света фонарей L5 (SetStatepropShadow) — обычные аддитивные куски города в матрице каждого фонаря.
Проверка: 206 фонарей из диска, центр пятна = место фонаря по xz (до 1 мм) и на 0,083 м выше основания, флаги куска 2 (полупрозрачное)
+ бит 24 (сложение №447) + 8 (двусторонний), цвет вершины = (0.73 0.71 0.52, альфа 0.6) по диску. Красный контроль:
SHR_LIGHTPOOL_OLD=1 -> 0 пятен (скрипт сам запускает контроль и требует, чтобы он был красным).
python3 tests/lightpool/gate.py   (из корня репозитория, нужны .venv и диск)"""
import os, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))

def run():
    import numpy as np
    import psp_export as PE
    from convert import Converter
    art = PE.GAME / 'art'; conv = Converter(); cache = {}; blob = []
    scenes = ['l5_terra'] + sorted(p.stem for p in art.glob('l5r*.p3d')) + sorted(p.stem for p in art.glob('l5z*.p3d'))
    for path in sorted(art.glob('l5*.p3d')): conv.resources(PE.read(path))
    got = []
    n, t = PE.lightpool_prims(5, scenes, art, conv, cache, blob, lambda prims, reg: got.append(prims), lambda s: -1)
    if os.environ.get('GATE_PRINT_ONLY'): print(f'pools={n}'); return 0
    ok = True
    def chk(c, msg):
        nonlocal ok
        print(('PASS ' if c else 'FAIL ') + msg); ok &= bool(c)
    chk(n == 206, f'206 фонарей с пятном (получено {n})')
    chk(t == 412, f'2 треугольника на пятно (получено {t})')
    cents = np.array([np.concatenate([p[2] for p in prims]).mean(0) for prims in got])
    pe = PE.prop_entities(scenes, art)
    names = ('l5_streetlamp', 'l5_streetlampold', 'l5_oldstreetlamp', 'l5_parkinglight', 'l5_streetlampsquare', 'l5_streetlampbanner')
    lamps = np.array([M[3, :3] for k, v in pe.items() if k.lower().replace('_shape', '') in names for M in v['mats']])
    d = np.array([np.hypot(*(cents[:, [0, 2]] - L[[0, 2]]).T).min() for L in lamps])
    chk(len(lamps) and d.max() < 1e-3, f'каждый фонарь PRP1 ({len(lamps)}) имеет пятно в своей точке (макс. {d.max():.5f} м)')
    dy = np.array([abs(cents[np.argmin(np.hypot(*(cents[:, [0, 2]] - L[[0, 2]]).T)), 1] - L[1] - 0.083) for L in lamps])
    chk(dy.max() < 0.02, f'высота пятна = основание + 0,083 м (макс. отклонение {dy.max():.4f} м)')
    fl = {int(p[1]) for prims in got for p in prims}
    chk(fl == {2 | 8 | (1 << 24)}, f'флаги куска только 2|8|бит24 (получено {sorted(fl)})')
    c = {int(p[4][0]) for prims in got for p in prims}
    chk(len(c) == 1 and (next(iter(c)) >> 24) in (0x99, 0x9a) and (next(iter(c)) & 0xFF) in (186, 187, 188), f'цвет вершины из диска: {[hex(x) for x in c]}')
    return 0 if ok else 1

if __name__ == '__main__':
    if os.environ.get('GATE_INNER'): sys.exit(run())
    env = dict(os.environ, GATE_INNER='1')
    r_new = subprocess.run([sys.executable, __file__], env=env).returncode
    env_old = dict(env, SHR_LIGHTPOOL_OLD='1', GATE_PRINT_ONLY='1')
    out = subprocess.run([sys.executable, __file__], env=env_old, capture_output=True, text=True).stdout
    red = 'pools=0' in out
    print(('PASS ' if red else 'FAIL ') + f'красный контроль SHR_LIGHTPOOL_OLD=1: {out.strip()}')
    sys.exit(0 if (r_new == 0 and red) else 1)
