#!/usr/bin/env python3
"""№301 (стены интерьеров): доля проб границы пола без стены. Проба: клетка пола 0,25 м у границы, три луча наружу (0,6/1,4/2,0 м над полом, 3 м), «дыра» —
ни один не встретил треугольник (tools/interior_export.py wall_probe). Считается по рисованию комнаты ПОСЛЕ достройки room_wall_fill.
  wall_fill.py gate [--level N]   красный (без ROOM_WALL_FILL=1: доля дыр у комнат выше DOLE_MIN) и зелёный (после достройки доля < DOLE_MAX): PASS / FAIL
  wall_fill.py _m [--level N]     внутренний вызов: печать «ROOMWALL имя проб дыр» на комнату"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DOLE_MAX, DOLE_MIN = 0.01, 0.05


def measure(level):
    import numpy as np
    sys.path.insert(0, str(ROOT / 'tools')); sys.argv = ['x', '--level', str(level), '--outdir', os.environ.get('WALL_FILL_OUT', '/tmp/wall_fill_out')]
    import interior_export as IE
    orig_ceil, orig_wall, state = IE.room_ceiling, IE.room_wall_fill, {}

    def wall(prims, TR, ci):
        wc, info = orig_wall(prims, TR, ci)
        allp = prims + wc
        T = np.concatenate([P.reshape(-1, 3, 3) for _, _, P, _, _ in allp]).astype(np.float64)
        g = np.asarray(TR, np.float64); g = g[g[:, 3, 1] > .7][:, :3]
        _, _, _, pr = IE.wall_probe(T, TR, float(g[:, :, 1].min()))
        name = f'{g[:, :, 0].min():.0f}_{g[:, :, 2].min():.0f}'
        print('ROOMWALL', name, len(pr), sum(1 for p in pr if p[4]), (info or {}).get('tris', 0))
        return wc, info
    IE.room_wall_fill = wall; IE.main()


def run(level, old):
    env = dict(os.environ, SHR_TEX_CAP256='1', SHR_SMALL_MIPS='1', SHR_LAYERS='1')
    if old: env.pop('ROOM_WALL_FILL', None)
    else: env['ROOM_WALL_FILL'] = '1'
    r = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '_m', '--level', str(level)], env=env, capture_output=True, text=True, cwd=ROOT)
    rows = [l.split() for l in r.stdout.splitlines() if l.startswith('ROOMWALL ')]
    if not rows: raise SystemExit('нет результата: ' + (r.stderr or r.stdout)[-400:])
    return {x[1]: (int(x[2]), int(x[3]), int(x[4])) for x in rows}


if __name__ == '__main__':
    level = int(sys.argv[sys.argv.index('--level') + 1]) if '--level' in sys.argv else 1
    if sys.argv[1:2] == ['_m']: measure(level); sys.exit(0)
    if sys.argv[1:2] != ['gate']: sys.exit(__doc__)
    old, new = run(level, True), run(level, False); bad = []
    for k in sorted(new):
        po, ho, _ = old[k]; pn, hn, tr = new[k]; fo, fn = ho / max(1, po), hn / max(1, pn)
        print(f'комната {k}: проб {po}→{pn}, дыр {ho} ({fo:.0%}) → {hn} ({fn:.1%}), добавлено треугольников {tr}')
        if fn >= DOLE_MAX: bad.append(f'{k}: после достройки дыр {fn:.1%}')
    red = [k for k in old if old[k][1] / max(1, old[k][0]) > DOLE_MIN]
    if not red: bad.append('красный контроль не пойман: прежний код нигде не даёт дыр > 5 %')
    print('PASS' if not bad else 'FAIL: ' + '; '.join(bad)); sys.exit(1 if bad else 0)
