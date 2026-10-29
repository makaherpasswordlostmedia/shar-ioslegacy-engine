#!/usr/bin/env python3
"""Сверка камер старта этапов миссий (правка Роба 40): движок (viewer/msncam.c по пакету msncam.shr, tests/camera/msncam_host.c)
против независимого разбора диска (анимация CAM_<камера> в p3d фазы через tools/frontend3d_export.anims, кадры 0, середина
и последний), против записи PS2 (камера m0sd — облёт улицы к дому Симпсонов: начало выше и дальше, конец у дома,
tools/ps2ref/CATALOG_L1.md 0:58–1:03) и против самих скриптов: камера каждой фазы кончается в 3–12 м от места, куда сценарий
ставит игрока на старте этой фазы (SetMissionResetPlayerOutCar / InCar, у гонок PlacePlayerCar), и смотрит на него — отсюда
правило «когда играть» (viewer/game_msn.c gameMsnStartCam). Плавность: скачок глаза за кадр 1/30 с не больше JUMP_MAX.
Поиск по фазе: своя камера находится, чужое имя камеры отвергается.

    python tests/camera/msncam_check.py HOST.txt        -> PASS / FAIL"""
import re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import msncam_export as M   # noqa: E402

JUMP_MAX = 2.0     # м за 1/30 с (облёт m0 — ~70 м за 4 с, ~0.6 м за кадр)
HOUSE = np.array([229.0, 184.0])
END_NEAR = 12.0    # м: конец камеры — у места игрока на старте фазы
LOOK_MAX = 50.0    # градусов между взглядом последнего кадра и направлением на это место


def placement(script):
    """локатор, куда сценарий ставит игрока на старте фазы (SetInitialWalk — куда он приходит от двери, m0sd)"""
    s = M._clean((M.GAME / 'scripts/missions/level01' / script).read_text(errors='replace'))
    for pat in (r'SetInitialWalk\s*\(\s*"([^"]+)"', r'SetMissionResetPlayerOutCar\s*\(\s*"([^"]+)"', r'SetMissionResetPlayerInCar\s*\(\s*"([^"]+)"',
                r'PlacePlayerCar\s*\(\s*"[^"]*"\s*,\s*"([^"]+)"'):
        m = re.search(pat, s)
        if m: return m.group(1)
    return None


def main():
    rows = open(sys.argv[1]).read().splitlines()
    if any(r.startswith('BAD') for r in rows): print('FAIL: ' + next(r for r in rows if r.startswith('BAD'))); return 1
    poses, finds = {}, {}
    for r in rows:
        p = r.split()
        if r.startswith('POSE '): poses.setdefault(p[1].lower(), []).append([float(x) for x in p[2:10]] + [int(p[10])])
        if r.startswith('FIND '): finds[p[1].lower()] = (p[2], p[3])
    fails, notes = [], []
    ref = {ph.lower(): (cam, p3d, script) for m, script, cam, p3d, ph in M.cameras(1)}
    import compile as C   # noqa: E402  локаторы уровня (как у компилятора миссий)
    locs = {}
    for d in C.Compiler(1).p3d_locs.values():
        for k, L in d.items(): locs.setdefault(k, np.array(L.pos))
    for ph, P in sorted(poses.items()):
        if ph not in ref: fails.append(f'{ph}: фазы нет в скриптах диска'); continue
        P = np.array(P); cam, p3d, script = ref[ph]; nfr, fps, R = M.frames(p3d, cam)
        for f in (0, nfr // 2, nfr - 1):
            t = f / fps; i = int(np.argmin(np.abs(P[:, 0] - t)))
            if abs(P[i, 0] - t) < 1e-3 and np.abs(P[i, 1:4] - R[f, :3]).max() > .01:
                fails.append(f'{ph} кадр {f}: глаз {np.round(P[i, 1:4], 2)} против диска {np.round(R[f, :3], 2)}')
        jump = np.linalg.norm(np.diff(P[:, 1:4], axis=0), axis=1).max()
        if jump > JUMP_MAX: fails.append(f'{ph}: скачок глаза {jump:.2f} м за кадр')
        if P[-1, 8] != 0: fails.append(f'{ph}: анимация не кончается')
        fd = finds.get(ph)
        if not fd or fd[0].lower() != cam.lower() or fd[1] != 'wrong-name-refused': fails.append(f'{ph}: поиск камеры по фазе {fd}')
        loc = placement(script); where = locs.get((loc or '').lower())
        if where is None: fails.append(f'{ph}: нет места игрока на старте фазы ({loc})'); continue
        end, look = P[-1, 1:4], P[-1, 4:7] - P[-1, 1:4]; to = where - end
        dist = float(np.linalg.norm(to[[0, 2]])); ang = float(np.degrees(np.arccos(np.clip(np.dot(look, to) / np.linalg.norm(look) / np.linalg.norm(to), -1, 1))))
        if dist > END_NEAR or ang > LOOK_MAX: fails.append(f'{ph}: конец камеры не у игрока ({loc}: {dist:.1f} м, {ang:.0f}°)')
        notes.append(f'{ph} {cam}: {nfr} кадров, {(nfr - 1) / fps:.1f} с, глаз {np.round(P[0, 1:4], 1)} -> {np.round(P[-1, 1:4], 1)}, '
                     f'FOV {P[0, 7]:.1f}°, шаг до {jump:.2f} м; конец в {dist:.1f} м от {loc}, взгляд {ang:.0f}°')
    missing = sorted(set(ref) - set(poses))
    if missing: fails.append('нет камер фаз: ' + ', '.join(missing))
    if 'm0sd' not in poses: fails.append('нет камеры m0sd (облёт на старте уровня)')
    else:
        P = np.array(poses['m0sd']); d0 = np.linalg.norm(P[0, [1, 3]] - HOUSE); d1 = np.linalg.norm(P[-1, [1, 3]] - HOUSE)
        notes.append(f'm0sd: до дома Симпсонов {d0:.0f} м -> {d1:.0f} м, высота {P[0, 2]:.1f} -> {P[-1, 2]:.1f} м')
        if not (d1 < 25 and d0 > d1 + 30 and P[0, 2] > P[-1, 2] + 5):
            fails.append('m0sd: не облёт улицы к дому Симпсонов (запись PS2: сверху издалека к дому)')
    print('FAIL: ' + fails[0] if fails else f'PASS: камеры старта {len(poses)} фаз — как на диске, каждая прилетает к месту игрока, m0 облетает улицу к дому')
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
