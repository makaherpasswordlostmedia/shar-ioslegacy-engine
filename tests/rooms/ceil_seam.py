#!/usr/bin/env python3
"""Правка Роба 301 (потолок дома, «перепады плоскостей»): щель на стыке достроенного потолка с потолком прихожей.
Для дома Симпсонов (комната в x 490…512, z > 384 пакета уровня 1) считаем клетки пола 5 см, над которыми нет потолка, видимого снизу
(лицом вниз, двустороннее или без отсечения), после достройки tools/interior_export.py room_ceiling. Зелёный: доля таких клеток < GAP_MAX;
красный контроль: тот же экспорт с ROOM_CEIL_SEAM_OLD=1 (прежняя клетка без захода под соседний потолок) обязан дать долю > GAP_MAX.
  ceil_seam.py gate    красный, потом зелёный: PASS / FAIL
  ceil_seam.py new|old одна половина (внутренний вызов)"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
GAP_MAX = 0.005


def measure():
    import numpy as np
    sys.path.insert(0, str(ROOT / 'tools')); sys.argv = ['x', '--level', '1', '--outdir', os.environ.get('CEIL_SEAM_OUT', '/tmp/ceil_seam_out')]
    import interior_export as IE
    orig, res = IE.room_ceiling, {}

    def wrap(prims, TR):
        caps, info = orig(prims, TR); allp = prims + caps
        T = np.concatenate([P.reshape(-1, 3, 3) for _, _, P, _, _ in allp]).astype(float)
        FL = np.concatenate([np.full(len(P) // 3, fl) for _, fl, P, _, _ in allp])
        if not (T[:, :, 0].min() > 490 and T[:, :, 0].max() < 512 and T[:, :, 2].min() > 384): return caps, info
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); ar = np.linalg.norm(n, axis=1) / 2; ny = n[:, 1] / np.maximum(1e-12, 2 * ar)
        g = np.asarray(TR, float); g = g[g[:, 3, 1] > .7][:, :3]; fl = g[:, :, 1].min()
        xs = np.arange(T[:, :, 0].min() + .025, T[:, :, 0].max(), .05); zs = np.arange(T[:, :, 2].min() + .025, T[:, :, 2].max(), .05)
        X, Z = np.meshgrid(xs, zs, indexing='ij'); Y0 = np.full(X.shape, np.inf); has = np.zeros(X.shape, bool)

        def cover(a, b, c):
            d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            if abs(d) < 1e-12: return None, None
            w1 = ((b[2] - c[2]) * (X - c[0]) + (c[0] - b[0]) * (Z - c[2])) / d; w2 = ((c[2] - a[2]) * (X - c[0]) + (a[0] - c[0]) * (Z - c[2])) / d
            w3 = 1 - w1 - w2; return (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6), w1 * a[1] + w2 * b[1] + w3 * c[1]
        for t in g:
            m, y = cover(*t)
            if m is not None: Y0 = np.where(m, np.minimum(Y0, y), Y0)
        vis = ((ny < -.5) | (((FL & 8) != 0) | ((FL & 128) == 0)) & (np.abs(ny) > .5)) & ((FL & 2) == 0) & (T[:, :, 1].min(1) >= fl + 2.3)
        for i in np.nonzero(vis)[0]:
            m, _ = cover(*T[i])
            if m is not None: has |= m
        flo = np.isfinite(Y0); res['cells'] = int(flo.sum()); res['gap'] = int((flo & ~has).sum())
        return caps, info
    IE.room_ceiling = wrap; IE.main()
    return res


def run(mode):
    env = dict(os.environ, SHR_TEX_CAP256='1', SHR_SMALL_MIPS='1', SHR_LAYERS='1')
    if mode == 'old': env['ROOM_CEIL_SEAM_OLD'] = '1'
    else: env.pop('ROOM_CEIL_SEAM_OLD', None)
    r = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '_m'], env=env, capture_output=True, text=True, cwd=ROOT)
    for l in r.stdout.splitlines():
        if l.startswith('CEILSEAM '): c, g = map(int, l.split()[1:3]); return c, g
    raise SystemExit('нет результата: ' + (r.stderr or r.stdout)[-400:])


if __name__ == '__main__':
    if sys.argv[1:] == ['_m']:
        r = measure(); print('CEILSEAM', r['cells'], r['gap']); sys.exit(0)
    if sys.argv[1:2] != ['gate']: sys.exit(__doc__)
    oc, og = run('old'); nc, ng = run('new')
    fo, fn = og / oc, ng / nc
    print(f'прежнее: щель {og} из {oc} клеток пола ({fo:.2%}); новое: {ng} из {nc} ({fn:.2%}); допуск {GAP_MAX:.1%}')
    ok = fo > GAP_MAX and fn < GAP_MAX
    print('PASS' if ok else ('FAIL: красный контроль не пойман (прежнее в допуске)' if fo <= GAP_MAX else 'FAIL: щель на стыке потолка осталась'))
    sys.exit(0 if ok else 1)
