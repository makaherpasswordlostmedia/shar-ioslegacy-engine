#!/usr/bin/env python3
"""Камеры зон города (правка Роба 40): пакет zonecam-l1.shr и движок (viewer/roomcam.c) против независимого разбора диска.

    python tests/camera/zonecam_check.py host HOST.txt [--expect-red]
        состав пакета = камеры города уровня 1 для пешего Гомера (StaticCam с Data 1/2 и все RailCam; Data 0 — прыжки машины —
        не в пакете); ноги Гомера в центре триггера камеры -> выбрана камера, чей триггер НА ДИСКЕ содержит эту точку;
        камера смотрит на Гомера (угол между взглядом и направлением на него < 20°), глаз не дальше 40 м
    python tests/camera/zonecam_check.py emu smoke.txt [--expect-red]
        сцена у двери дома Симпсонов (tests/camera/zonecam_scenario.txt): снимает z1_cam1, глаз — в точке локатора
        (запись PS2 12:23: неподвижная камера со двора на дверь)"""
import math, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()


def disc():
    """{имя: (вид 12|4, Data или None, [триггеры], позиция)} — камеры города уровня 1, разбор диска (p3dlocs + данные локатора)"""
    from p3d import read, walk, string
    from p3dlocs import read_locators
    out = {}
    for f in sorted(GAME.glob('art/l1*.p3d')):
        if f.stem[2] == 'i': continue
        L, _ = read_locators(f, f.name); T = {l.name: l for l in L}
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            name, p = string(c.data); kind, ln = struct.unpack_from('<II', c.data, p)
            if kind == 12 and ln >= 10:
                data = struct.unpack_from('<10I', c.data, p + 8)[9]
                out[name] = (12, data, T[name].triggers, np.array(T[name].pos))
            elif kind == 4 and any(s.id == 0x3000007 and any(r.id == 0x300000a for r in s.children) for s in c.children):
                out[name] = (4, None, T[name].triggers, np.array(T[name].pos))
    return out


def inside(trig, p):
    rect, c, half, axes = trig
    d = np.array(p) - np.array(c)
    if not rect: return np.linalg.norm(d) <= half[0] + 1e-3
    return all(abs(d @ np.array(a)) <= h + 1e-3 for a, h in zip(axes, half))


def main():
    mode, path = sys.argv[1], sys.argv[2]; red = '--expect-red' in sys.argv
    D = disc(); fails, notes = [], []
    foot = {n for n, v in D.items() if not (v[0] == 12 and v[1] == 0)}; car = set(D) - foot
    if mode == 'host':
        rows = open(path).read().splitlines()
        if any(r.startswith('BAD') for r in rows): fails.append(next(r for r in rows if r.startswith('BAD')))
        names = {r.split()[1] for r in rows if r.startswith('CAM ')}
        if names != foot: fails.append(f'состав пакета: лишние {sorted(names - foot)}, нет {sorted(foot - names)}')
        if names & car: fails.append(f'в пакете камеры машины {sorted(names & car)}')
        for r in rows:
            if not r.startswith('PICK '): continue
            p = r.split(); want, got = p[1], p[2]; e = np.array(list(map(float, p[3:6]))); l = np.array(list(map(float, p[6:9])))
            fy = float(p[9]); q = np.array(list(map(float, p[10:13])))
            if got == '-' or got not in D: fails.append(f'{want}: в центре триггера камера не выбрана'); continue
            if not any(inside(t, q) for t in D[got][2]): fails.append(f'{want}: выбрана {got}, но её триггер на диске не содержит точку'); continue
            h = q + [0, 1.0, 0]; a, b = l - e, h - e
            ang = math.degrees(math.acos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9), -1, 1)))
            dist = float(np.linalg.norm(b))
            if ang > 20 or dist > 40: fails.append(f'{want} ({got}): не на Гомера — угол {ang:.0f}°, {dist:.1f} м'); continue
            notes.append(f'{want}: выбрана {got}, на Гомера {ang:.0f}°, {dist:.1f} м, FOV {fy:.0f}°')
    else:
        rows = [r for r in open(path, errors='replace').read().splitlines() if r.startswith('ZONECAM ')]
        door = next((r for r in rows if 'cam=z1_cam1' in r), None)
        if not door: fails.append('у двери дома Симпсонов камера z1_cam1 не включилась')
        else:
            kv = dict(x.split('=', 1) for x in door.split()[1:]); e = np.array(list(map(float, kv['eye'].split(','))))
            d = float(np.linalg.norm(e - D['z1_cam1'][3]))
            if d > 0.2: fails.append(f'z1_cam1: глаз {np.round(e, 2)} не в точке локатора {np.round(D["z1_cam1"][3], 2)} ({d:.2f} м)')
            else: notes.append(f'z1_cam1 у двери: глаз в точке локатора ({d * 100:.0f} см), {door.strip()}')
        notes += [r.strip() for r in rows[:8]]
    if red:
        ok = bool(fails); print(('PASS (красный пойман): ' + fails[0]) if ok else 'FAIL (красный не пойман)'); return 0 if ok else 1
    print(('FAIL: ' + fails[0]) if fails else f'PASS: камеры зон — {len(foot)} пешком как на диске ({len(car)} машины не в пакете)')
    for f in fails[1:8]: print('  ещё: ' + f)
    for n in notes[:40]: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
