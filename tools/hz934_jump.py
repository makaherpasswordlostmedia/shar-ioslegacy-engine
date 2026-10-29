#!/usr/bin/env python3
# №934 (HOR2): скачок ленты при смене клетки — аналитически по horizon.shr (HOR1 + хвост DST2), без эмулятора; те же формулы, что в viewer/horizon.h.
# Для каждой пары соседних клеток (центры ≤ 70 м) с перепадом ey ≥ MINDEY глаз идёт по прямой между центрами (высота глаза — линейно между ey клеток: склон), шаг 3 м, ±15 м около границы. На каждом шаге строится верхняя кромка ленты в системе
# «азимут от глаза → угол места»: старая лента (--old): ближайшая клетка, вершина на азимуте клетки, угол = atan(tan + (ey клетки − ey глаза)/(drawDist+4)) (без горизонтального параллакса, смена клетки скачком);
# новая: мировые точки контура (cx + D sin a, ey + tan·D, cz − D cos a) двух ближайших клеток на общей сетке азимутов (2°) с подмесом (вторая получает 0…0,5 в полосе W = 20 м у границы), проекция с глаза.
# Скачок = |кромка(шаг) − кромка(шаг − 3 м)| по сетке азимутов 0,5°; на пару берётся наибольший p90 по шагам. Вывод: худшие пары и итог; код 1, если максимум p90 по парам > LIM (по умолчанию 5°)
# hz934_jump.py horizon.shr [--dd 150] [--set 1] [--mindey 10] [--lim 5] [--old] [--step 3] [--w 20]
import sys, struct, math, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dd', type=float, default=150.); ap.add_argument('--set', type=int, default=1); ap.add_argument('--mindey', type=float, default=10.); ap.add_argument('--lim', type=float, default=5.)
ap.add_argument('--old', action='store_true'); ap.add_argument('--emit', type=int, default=0, help='напечатать K худших пар строками PAIR x1 z1 ey1 x2 z2 ey2 (для сценария эмулятора)'); ap.add_argument('--step', type=float, default=3.); ap.add_argument('--w', type=float, default=40.); a = ap.parse_args()
d = open(a.file, 'rb').read(); n = struct.unpack_from('<I', d, 4)[0]; R = a.dd + 4.0
assert d[-16:-12] == b'DSTF', 'нет хвоста DST2'; DQ = 130. * 1.19 ** np.arange(16); t0 = struct.unpack_from('<I', d, len(d) - 12)[0]
cells = []
for i in range(n):
    cx, cz, ey, nv, off, p0, p1, p2 = struct.unpack_from('<3f5I', d, 32 + 32 * i); o0 = struct.unpack_from('<I', d, t0 + 16 + 4 * i)[0]
    use2 = a.set == 1 and p2 > 0; cnt = p2 if use2 else nv; vo = p1 if use2 else off; do = o0 + (nv + 1) // 2 if use2 else o0
    v = np.array(struct.unpack_from('<' + 'Hh' * cnt, d, vo), dtype=np.float64).reshape(-1, 2); nb_ = np.frombuffer(d, np.uint8, (cnt + 1) // 2, t0 + do)
    D = DQ[np.stack([nb_ & 15, nb_ >> 4], 1).reshape(-1)[:cnt]]
    cells.append((cx, cz, ey, v[:, 0], v[:, 1] / 16384., D))
RN = 180; AJ = np.arange(RN + 1) * (65536. / RN); AZ = np.arange(720) * (2 * math.pi / 720)
def resample(c):   # контур клетки на общую сетку азимутов 2°: мировые точки (как HzRs в horizon.h)
    cx, cz, ey, az, t, D = c; ax = np.r_[az, az[0] + 65536.]; tx = np.r_[t, t[0]]; Dx = np.r_[D, D[0]]; aj = np.where(AJ < az[0], AJ + 65536., AJ)
    tt = np.interp(aj, ax, tx); dd = np.interp(aj, ax, Dx); ang = AJ * (2 * math.pi / 65536.)
    return np.stack([cx + dd * np.sin(ang), ey + tt * dd, cz - dd * np.cos(ang)], 1)
rs = [resample(c) for c in cells]
def project(P, ex, ey, ez):   # мировые точки (по сетке азимутов клетки) -> кромка по азимуту глаза
    dx = P[:, 0] - ex; dz = P[:, 2] - ez; az = np.arctan2(dx, -dz) % (2 * math.pi); el = np.arctan((P[:, 1] - ey) / np.maximum(np.hypot(dx, dz), 1.))
    o = np.argsort(az); az = az[o]; el = el[o]; return np.interp(AZ, np.r_[az - 2 * math.pi, az, az + 2 * math.pi], np.r_[el, el, el])
def edge_old(c, eyy):
    cx, cz, ey, az, t, D = c; a2 = az * (2 * math.pi / 65536.); return np.arctan(np.interp(AZ, np.r_[a2 - 2 * math.pi, a2, a2 + 2 * math.pi], np.r_[t, t, t]) + (ey - eyy) / R)
xy = np.array([(c[0], c[1]) for c in cells]); res = []
for i in range(n):
    for j in range(i + 1, n):
        if math.hypot(xy[i, 0] - xy[j, 0], xy[i, 1] - xy[j, 1]) > 70 or abs(cells[i][2] - cells[j][2]) < a.mindey: continue
        ci, cj = cells[i], cells[j]; L = math.hypot(cj[0] - ci[0], cj[1] - ci[1]); ux, uz = (cj[0] - ci[0]) / L, (cj[1] - ci[1]) / L; edges = []
        for s in np.arange(L / 2 - 15, L / 2 + 15 + 1e-6, a.step):   # s — расстояние от центра i вдоль прямой
            ex_, ez_ = ci[0] + ux * s, ci[1] + uz * s; ey_ = ci[2] + (cj[2] - ci[2]) * (s / L)
            d1, d2 = s, L - s
            if a.old: edges.append(edge_old(ci if d1 <= d2 else cj, ey_))
            else:
                (k1, k2, da, db) = (i, j, d1, d2) if d1 <= d2 else (j, i, d2, d1); w2 = 0.5 * min(1., max(0., (da + a.w - db) / a.w))
                edges.append(project((1 - w2) * rs[k1] + w2 * rs[k2], ex_, ey_, ez_))
        jm = [float(np.percentile(np.degrees(np.abs(edges[q + 1] - edges[q])), 90)) for q in range(len(edges) - 1)]; res.append((max(jm), i, j))
res.sort(reverse=True)
for p90, i, j in res[:a.emit]: print('PAIR %.2f %.2f %.2f %.2f %.2f %.2f %.1f' % (cells[i][0], cells[i][1], cells[i][2], cells[j][0], cells[j][1], cells[j][2], p90))
for p90, i, j in res[:8]: print(f'({cells[i][0]:.0f};{cells[i][1]:.0f}) ey {cells[i][2]:.0f} -> ({cells[j][0]:.0f};{cells[j][1]:.0f}) ey {cells[j][2]:.0f}: p90 скачка за шаг {a.step:.0f} м {p90:.1f}°')
if res:
    P = np.array([r[0] for r in res]); print(f'ИТОГ ({"старая" if a.old else "новая"} лента): пар {len(res)}, p90 скачка за шаг: медиана {np.median(P):.1f}°, p95 {np.percentile(P, 95):.1f}°, макс {P.max():.1f}°')
    ok = P.max() <= a.lim; print('HZ934-СКАЧКИ:', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
print('нет пар'); sys.exit(1)
