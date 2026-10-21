#!/usr/bin/env python3
"""Камеры старта фаз миссий в эмуляторе (правка Роба 40; сценарий tests/camera/startcam_scenario.txt, запуск
tests/camera/startcam_emu.sh). По строкам smoke.txt:
  MSNCAM req phase=.. cam=.. found=.. play=..   — заявка крючка миссий (viewer/game_msn.c gameMsnStartCam)
  MSNCAM start mN имя phase=..                  — камера пошла; MSNCAM end / MSNCAM skip — кончилась / пропущена X
  MSNCAMP t= ct= phase= eye= look= fovy= homer= car=   — каждый кадр камеры: глаз, как нарисован, и где игрок
Проверки на каждую фазу m0sd..m7sd: заявка пришла с именем камеры из данных фазы и камера пошла; глаз в каждом кадре
совпадает с анимацией диска в момент ct (независимый разбор tools/msncam_export.frames, допуск 5 см); игрок стоит (Гомер и
машина сдвинулись меньше 5 см за всю камеру); камера кончилась сама (m2sd — пропуск X раньше конца); Гомер на старте
камеры — у места игрока из скрипта фазы (SetInitialWalk / SetMissionReset*, до 3 м): камера играет ПОСЛЕ того, как
сценарий поставил игрока.

    python tests/camera/startcam_check.py smoke.txt [--expect-red]"""
import re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
sys.path.insert(0, str(ROOT / 'tests/camera'))
import msncam_export as M   # noqa: E402
import msncam_check as MC   # noqa: E402  место игрока на старте фазы (тот же разбор скриптов)

PHASES = [f'm{i}sd' for i in range(8)]
SKIPPED = {'m2sd'}
EYE_TOL, FROZEN = 0.05, 0.05


def v3(s): return np.array([float(x) for x in s.split(',')])


def main():
    red = '--expect-red' in sys.argv
    phases = PHASES
    if '--phases' in sys.argv: phases = sys.argv[sys.argv.index('--phases') + 1].split(',')
    rows = open(sys.argv[1], errors='replace').read().splitlines()
    ref = {ph.lower(): (cam, p3d, script) for m, script, cam, p3d, ph in M.cameras(1)}
    import compile as C   # noqa: E402
    locs = {}
    for d in C.Compiler(1).p3d_locs.values():
        for k, L in d.items(): locs.setdefault(k, np.array(L.pos))
    req, start, end, skip, fr = {}, {}, {}, {}, {}
    cur = None
    for r in rows:
        if r.startswith('MSNCAM req '):
            kv = dict(x.split('=', 1) for x in r.split()[2:] if '=' in x); req[kv['phase'].lower()] = kv
        elif r.startswith('MSNCAM start '):
            kv = dict(x.split('=', 1) for x in r.split()[2:] if '=' in x); cur = kv['phase'].lower(); start[cur] = r
        elif r.startswith('MSNCAM end') and cur: end[cur] = r
        elif r.startswith('MSNCAM skip') and cur: skip[cur] = r
        elif r.startswith('MSNCAMP '):
            kv = dict(x.split('=', 1) for x in r.split()[1:]); fr.setdefault(kv['phase'].lower(), []).append(kv)
    fails, notes = [], []
    for ph in phases:
        cam, p3d, script = ref[ph]
        q = req.get(ph)
        if not q: fails.append(f'{ph}: крючок миссий не заявил камеру'); continue
        if q.get('cam', '').lower() != cam.lower() or q.get('found') != '1' or q.get('play') != '1':
            fails.append(f'{ph}: заявка {q} (данные: {cam})'); continue
        F = fr.get(ph, [])
        if ph not in start or len(F) < 10: fails.append(f'{ph}: камера не пошла ({len(F)} кадров)'); continue
        nfr, fps, R = M.frames(p3d, cam); err = 0.0
        for k in F:
            f = min(max(float(k['ct']) * fps, 0.0), nfr - 1); i = min(int(f), nfr - 2); u = f - i
            want = R[i, :3] * (1 - u) + R[i + 1, :3] * u
            err = max(err, float(np.abs(v3(k['eye']) - want).max()))
        if err > EYE_TOL: fails.append(f'{ph}: глаз отличается от анимации диска на {err:.2f} м')
        H = np.array([v3(k['homer']) for k in F]); Cr = np.array([v3(k['car']) for k in F])
        moved = max(float(np.ptp(H, axis=0).max()), float(np.ptp(Cr, axis=0).max()))
        if moved > FROZEN: fails.append(f'{ph}: игрок не стоит под камерой (сдвиг {moved:.2f} м)')
        dur = (nfr - 1) / fps; ct = float(F[-1]['ct'])
        if ph in SKIPPED:
            if ph not in skip or ct > dur - 0.3: fails.append(f'{ph}: пропуск X не сработал (кадр {ct:.2f} из {dur:.2f} с)')
        elif ph not in end or ct < dur - 0.1: fails.append(f'{ph}: камера не доиграла (последний кадр {ct:.2f} из {dur:.2f} с)')
        loc = MC.placement(script); where = locs.get((loc or '').lower())
        dh = float(np.linalg.norm((H[0] - where)[[0, 2]])) if where is not None else 1e9
        if dh > 3.0: fails.append(f'{ph}: Гомер на старте камеры не у места фазы {loc} ({dh:.1f} м)')
        notes.append(f'{ph} {cam}: {len(F)} кадров, глаз как на диске (до {err * 100:.1f} см), игрок стоит ({moved * 100:.1f} см), '
                     f'Гомер у {loc} ({dh:.1f} м), {"пропуск X" if ph in skip else "доиграла"}')
    if red:
        ok = bool(fails)
        print(('PASS (красный пойман): ' + fails[0]) if ok else 'FAIL (красный не пойман)'); return 0 if ok else 1
    print(('FAIL: ' + fails[0]) if fails else f'PASS: камеры старта {len(notes)} фаз — с крючка миссий, как на диске, игрок стоит')
    for f in fails[1:10]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
