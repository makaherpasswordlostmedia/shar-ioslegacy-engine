#!/usr/bin/env python3
"""Правка Роба 293: замер по данным — куски гостиной с флагом F_MENUHID (16, «не виден из камеры меню»), которые движок включает в
ПЕРВОМ кадре движения перелёта NEW GAME (FEFR тура TEST 9: pc 306 -> 604, floor 4 -> 6). Только чтение build/fe.shr.
  python3 tests/fe_guard/menuhid_floor.py [fe.shr] [--tl 2.124,3.13,...]
Печатает: куски пола (текстура floor3), их флаги, плоскость, перекрытие скрытых треугольников пола с видимыми в плане (доля точек
скрытого треугольника внутри видимых, края не в счёт), и где скрытые куски пола на экране 480×272 в позах перелёта (по умолчанию —
позы настоящего перелёта с PSP, TEST 9): пикселей внутри экрана (растр центров пикселей), рамка вершин."""
import struct, sys, math
import numpy as np

F_MENUHID = 16


def load(path):
    d = open(path, 'rb').read()
    h = struct.unpack_from('<4s13If2I12f3I', d, 0)
    nTex, offTex, nPiece, offPiece, nTrack, offTrack = h[3], h[4], h[5], h[6], h[7], h[8]
    nFrames, offCam, menu, offNames = h[11], h[12], h[13], h[31]
    names = [d[offNames + 32 * i:offNames + 32 * i + 32].split(b'\0')[0].decode('latin1') for i in range(nTex)]
    P = []
    for i in range(nPiece):
        o = offPiece + 64 * i
        tex, ttr, fl, node, vis, _, nv, ov = struct.unpack_from('<6H2I', d, o)
        f = struct.unpack_from('<4f6f', d, o + 20)
        q = np.frombuffer(d, np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')]), nv, ov)
        s = f[3] * (32768. / 32767.) / 32768.
        V = np.stack([q['x'], q['y'], q['z']], 1).astype(np.float64) * s + np.array(f[0:3])
        P.append(dict(i=i, tex=names[tex] if tex != 0xffff else '-', fl=fl, node=node, V=V))
    cam = np.frombuffer(d, '<f4', nFrames * 12, offCam).reshape(-1, 12).astype(np.float64)
    return P, cam, menu


def view(cam, tl):
    f0 = int(tl); f1 = min(f0 + 1, len(cam) - 1); c = cam[f0] + (cam[f1] - cam[f0]) * (tl - f0)
    cp = c[0:3]; cf = c[3:6] / np.linalg.norm(c[3:6]); cr = np.cross(cf, c[6:9]); cr /= np.linalg.norm(cr); cu = np.cross(cr, cf)
    tvy = math.tan(c[9] * .5) * .75
    return cp, cf, cr, cu, tvy * 16 / 9, tvy, c[10]


def inside2(px, pz, a, b, c, eps=1e-6):
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if abs(d) < 1e-12: return np.zeros_like(px, bool)
    l1 = ((px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (pz - a[1])) / d
    l2 = ((b[0] - a[0]) * (pz - a[1]) - (px - a[0]) * (b[1] - a[1])) / d
    return (l1 > eps) & (l2 > eps) & (1 - l1 - l2 > eps)


def main():
    path = next((a for a in sys.argv[1:] if a.endswith('.shr')), 'build/fe.shr')
    tls = [380.0, 1.0, 2.124, 3.130, 4.126, 5.126, 8.130, 10.132, 15.137, 20.142]
    if '--tl' in sys.argv: tls = [float(x) for x in sys.argv[sys.argv.index('--tl') + 1].split(',')]
    P, cam, menu = load(path)
    fl = [p for p in P if p['tex'].startswith('floor3')]
    hid = [p for p in fl if p['fl'] & F_MENUHID]; vis = [p for p in fl if not p['fl'] & F_MENUHID]
    print(f'куски пола floor3: {len(fl)} (видимых из меню {len(vis)}, F_MENUHID {len(hid)}); всего F_MENUHID кусков '
          f'{sum(1 for p in P if p["fl"] & F_MENUHID)}, треугольников {sum(len(p["V"]) // 3 for p in P if p["fl"] & F_MENUHID)}')
    for p in fl:
        y = p['V'][:, 1]
        print(f"  кусок {p['i']:4d} флаги {p['fl']:3d}{' F_MENUHID' if p['fl'] & F_MENUHID else ''} треуг {len(p['V']) // 3:3d} y {y.min():+.4f}..{y.max():+.4f}")
    VT = [p['V'][k:k + 3] for p in vis for k in range(0, len(p['V']), 3)]
    for p in hid:
        for k in range(0, len(p['V']), 3):
            T = p['V'][k:k + 3]; a, b, c = T[:, [0, 2]]
            w = np.random.default_rng(1).dirichlet([1, 1, 1], 4000); S = w @ T[:, [0, 2]]
            cov = np.zeros(len(S), bool)
            for U in VT: cov |= inside2(S[:, 0], S[:, 1], *U[:, [0, 2]])
            print(f"  скрытый {p['i']} треуг {k // 3}: доля внутри видимых треугольников пола {cov.mean() * 100:.2f} % (наложения нет, если 0)")
    gx, gy = np.meshgrid(np.arange(480) + .5, np.arange(272) + .5)
    for tl in tls:
        cp, cf, cr, cu, tvx, tvy, near = view(cam, tl); out = []
        for p in hid:
            rel = p['V'] - cp; z = rel @ cf; x = rel @ cr; y = rel @ cu
            sx = 240 + x / z / tvx * 240; sy = 136 - y / z / tvy * 136; px = 0
            for k in range(0, len(sx), 3):
                if (z[k:k + 3] <= near).any(): continue
                px += int(inside2(gx, gy, (sx[k], sy[k]), (sx[k + 1], sy[k + 1]), (sx[k + 2], sy[k + 2]), -1e-9).sum())
            out.append(f"кусок {p['i']}: пикселей {px}, вершины x {sx.min():.0f}..{sx.max():.0f} y {sy.min():.0f}..{sy.max():.0f}")
        print(f"  поза {tl:7.3f}: " + '; '.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
