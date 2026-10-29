#!/usr/bin/env python3
"""Дальняя плоскость комнат (viewer/main_rooms.h ROOM_FAR) не режет рисование комнаты: у обсерватории L3/L6 фон int_obv_background (панели в 40–120 м за комнатой,
виден в окнах и куполе) целиком лежал за 60 м и показывал фон комнаты. Для каждой комнаты уровня считаем наибольшее расстояние от точек пола до вершин
рисования; ROOM_FAR обязана быть не меньше. Красный контроль: прежние 60 м (ROOM_FAR_OLD=1) обязаны провалить обсерваторию.
  room_far.py gate [--level N ...]   по умолчанию L1 и L3: PASS / FAIL"""
import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def far_value(old):
    s = (ROOT / 'viewer/main_rooms.h').read_text()
    m = re.search(r'#define ROOM_FAR \(ROOM_FAR_OLD \? ([\d.]+)f : ([\d.]+)f\)', s)
    if not m: raise SystemExit('ROOM_FAR не найден в viewer/main_rooms.h')
    return float(m.group(1) if old else m.group(2))


def measure(level):
    import numpy as np
    sys.path.insert(0, str(ROOT / 'tools')); sys.argv = ['x', '--level', str(level), '--outdir', os.environ.get('ROOM_FAR_OUT', '/tmp/room_far_out')]
    import interior_export as IE
    orig = IE.room_ceiling

    def wrap(prims, TR):
        T = np.concatenate([P.reshape(-1, 3) for _, fl, P, _, _ in prims if (fl & 2) == 0]).astype(np.float64)
        g = np.asarray(TR, np.float64); g = g[g[:, 3, 1] > .7][:, :3].reshape(-1, 3)
        lo, hi = g.min(0), g.max(0); c = [lo, hi, (lo + hi) / 2, np.array([lo[0], lo[1], hi[2]]), np.array([hi[0], lo[1], lo[2]])]
        far = max(float(np.linalg.norm(T - p, axis=1).max()) for p in c)
        print('ROOMFAR', f'{lo[0]:.0f}_{lo[2]:.0f}', f'{far:.1f}')
        return orig(prims, TR)
    IE.room_ceiling = wrap; IE.main()


if __name__ == '__main__':
    if sys.argv[1:2] == ['_m']: measure(int(sys.argv[2])); sys.exit(0)
    if sys.argv[1:2] != ['gate']: sys.exit(__doc__)
    levels = [int(sys.argv[i + 1]) for i, a in enumerate(sys.argv) if a == '--level'] or [1, 3]
    env = dict(os.environ, SHR_TEX_CAP256='1', SHR_SMALL_MIPS='1', SHR_LAYERS='1'); worst = {}
    for lv in levels:
        r = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '_m', str(lv)], env=env, capture_output=True, text=True, cwd=ROOT)
        for l in r.stdout.splitlines():
            if l.startswith('ROOMFAR '): _, k, v = l.split(); worst[f'L{lv} {k}'] = float(v)
    if not worst: raise SystemExit('нет данных: ' + r.stderr[-300:])
    new, old = far_value(False), far_value(True); bad = []; red = []
    for k, v in sorted(worst.items()):
        print(f'комната {k}: наибольшее расстояние до рисования {v:.0f} м; ROOM_FAR {new:.0f} (прежнее {old:.0f})')
        if v > new: bad.append(f'{k}: {v:.0f} м > {new:.0f}')
        if v > old: red.append(k)
    if not red: bad.append('красный контроль не пойман: прежние 60 м нигде не режут')
    print('PASS (красный пойман у ' + ', '.join(red) + ')' if not bad else 'FAIL: ' + '; '.join(bad)); sys.exit(1 if bad else 0)
