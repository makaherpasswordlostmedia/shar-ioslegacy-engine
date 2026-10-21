"""Шаг 0 аудита (docs/АУДИТ_ОПТИМИЗАЦИИ_2026-09-27.md): данные для микробенча GE tests/gebench.

Берёт из build/level.shr вид худшего кадра bench v8 (точка 345 -81, курс 1), повторяет отсечение движка
(PVS, пирамида, дальность 115 м, LOD 50 м) и пишет build/gebench/cell.bin с пятью наборами геометрии:
  0 A — как в движке: исходные вершины (порядок np.unique), индексированный список;
  1 B — список, вершины переупорядочены по первому использованию;
  2 C — полосы (greedy, обход сохранён), склеены вырожденными треугольниками, индексированные,
        вершины по первому использованию в полосе;
  3 D — те же полосы без индексов (вершины развёрнуты);
  4 F — как C, но обход треугольников по кускам исправлен под отсечение задних граней (по видимости в этом виде).
Плюс разбор обхода: программный растр вида 240x136, какие видимые пиксели дают треугольники с «чужим» обходом.

python tools/strips.py [--level build/level.shr] [--out build/gebench/cell.bin] [--view 345 -81 1]
"""
import argparse, math, os, struct, sys
from collections import defaultdict
import numpy as np

VERT = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')])
FOVY, ASPECT, ZNEAR, DRAW, LOD = 62.0, 16.0 / 9.0, 0.7, 115.0, 50.0


def a16(n): return (n + 15) & ~15


# ---------------- чтение level.shr ----------------
def read_level(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'SHR7', 'level.shr: не SHR7'
    ntex, npc = struct.unpack_from('<II', b, 4)
    hd = struct.unpack_from('<14f', b, 12)
    hw, hh = struct.unpack_from('<ii', b, 12 + 14 * 4)
    table, ncell, cellOff, pvsOff = struct.unpack_from('<IIII', b, 76)
    L = dict(b=b, ntex=ntex, npc=npc, sph=hd[9], hox=hd[11], hoz=hd[12], hcell=hd[13], hw=hw, hh=hh)
    p = 104
    L['hm'] = np.frombuffer(b, '<i2', hw * hh * 4, p).reshape(hh, hw, 4); p = a16(p + hw * hh * 8)
    p = a16(p + hw * hh * 4)                                      # стены
    tex = []
    for i in range(ntex):
        w, h, lv = struct.unpack_from('<HHH', b, p)
        pal = b[p + 16:p + 16 + 1024]; p += 16 + 1024
        levels, lw, lh = [], w, h
        for l in range(lv):
            levels.append((lw, lh, b[p:p + lw * lh])); p = a16(p + lw * lh)
            lw >>= 1; lh = lh >> 1 if lh > 1 else 1
        tex.append(dict(w=w, h=h, pal=pal, levels=levels))
    L['tex'] = tex
    cells = [struct.unpack_from('<6f6I', b, cellOff + 48 * i) for i in range(ncell)]
    pcs = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, table + 80 * i)
        pc = dict(i=i, bb=r[0:6], tex=r[6], flags=r[7], nv=r[8], ni=r[9], owner=r[10], o=r[11:14], sc=r[14],
                  off=r[15], nf=r[16], cell=r[17])
        base = cells[pc['cell']][9] + pc['off']                  # смещение клетки в файле + кусок в клетке
        pc['v'] = np.frombuffer(b, VERT, pc['nv'], base)
        ib = base + a16(pc['nv'] * 16)
        pc['idx'] = np.frombuffer(b, '<u2', pc['ni'], ib)
        pc['fidx'] = np.frombuffer(b, '<u2', pc['nf'], ib + a16(pc['ni'] * 2))
        pcs.append(pc)
    L['pc'] = pcs
    L['pvs'] = None
    if pvsOff and b[pvsOff:pvsOff + 4] == b'PVS1':
        ox, oz, cs = struct.unpack_from('<3f', b, pvsOff + 4); W, H, pool = struct.unpack_from('<3I', b, pvsOff + 16)
        ent = np.frombuffer(b, '<u4', W * H * 2, pvsOff + 32).reshape(-1, 2)
        pl = np.frombuffer(b, '<u2', pool, pvsOff + 32 + W * H * 8)
        L['pvs'] = (ox, oz, cs, W, H, ent, pl)
    return L


# ---------------- вид и отсечение, как в viewer/main.c ----------------
def bench_points(L):
    st = int(50.0 / L['hcell']); hw, hh = L['hw'], L['hh']; pts = []
    gz, row = st // 2, 0
    while gz < hh:
        for j in range(hw // st + 1):
            gx = st // 2 + ((hw // st - j) if row & 1 else j) * st
            if gx < 0 or gx >= hw: continue
            c = [v for v in L['hm'][gz, gx] if v != -32768]
            if not c: continue
            pts.append((L['hox'] + (gx + .5) * L['hcell'], min(c) * .01, L['hoz'] + (gz + .5) * L['hcell']))
        gz += st; row += 1
    return pts


def camera(L, vx, vz, head):
    pts = bench_points(L)
    x, y, z = min(pts, key=lambda p: (p[0] - vx) ** 2 + (p[2] - vz) ** 2)
    h = L['sph'] + head * math.pi * .5
    eye = np.array([x - math.sin(h) * 7.5, y + 3.2, z - math.cos(h) * 7.5])
    f = np.array([x, y + 1.4, z]) - eye; f /= np.linalg.norm(f)
    return (x, y, z), eye, f


def planes(f):
    fx, fy, fz = f
    rx, rz = -fz, fx; rl = math.hypot(rx, rz); rx /= rl; rz /= rl
    ux, uy, uz = -rz * fy, rz * fx - rx * fz, rx * fy
    tv = math.tan(FOVY * .5 * math.pi / 180) * 1.03; th = tv * ASPECT
    return [(fx * th - rx, fy * th, fz * th - rz), (fx * th + rx, fy * th, fz * th + rz),
            (fx * tv - ux, fy * tv - uy, fz * tv - uz), (fx * tv + ux, fy * tv + uy, fz * tv + uz)]


def vis_box(b, pl, e):
    for n in pl:
        px = (b[3] if n[0] > 0 else b[0]) - e[0]; py = (b[4] if n[1] > 0 else b[1]) - e[1]; pz = (b[5] if n[2] > 0 else b[2]) - e[2]
        if px * n[0] + py * n[1] + pz * n[2] < 0: return False
    return True


def box_d2(b, e):
    d = 0.0
    for a in range(3):
        lo, hi = b[a], b[a + 3]
        t = lo - e[a] if lo - e[a] > 0 else (e[a] - hi if e[a] - hi > 0 else 0)
        d += t * t
    return d


def cull(L, eye, f, lod):
    pl = planes(f); cand = None
    if L['pvs']:
        ox, oz, cs, W, H, ent, pool = L['pvs']
        gx, gz = int(math.floor((eye[0] - ox) / cs)), int(math.floor((eye[2] - oz) / cs))
        if 0 <= gx < W and 0 <= gz < H and ent[gz * W + gx][1] != 0xFFFFFFFF:
            s, n = ent[gz * W + gx]; cand = [int(k) for k in pool[s:s + n]]
    if cand is None: cand = [p['i'] for p in L['pc'] if p['owner'] == 0]
    out = []
    for k in cand:
        p = L['pc'][k]
        if p['owner'] != 0: continue
        d2 = box_d2(p['bb'], eye)
        if d2 > DRAW * DRAW or not vis_box(p['bb'], pl, eye): continue
        far = d2 > LOD * LOD and lod
        ix = p['fidx'] if far else p['idx']
        if len(ix) == 0: continue
        t = p['tex'] if 0 <= p['tex'] <= 510 else 511
        out.append((((p['flags'] & 3) << 9) | t, k, far))
    out.sort(key=lambda r: r[0])                                  # сортировка подсчётом в движке стабильна
    return [(k, far) for _, k, far in out]


# ---------------- полосы ----------------
def stripify(tris):
    """greedy: треугольники (a,b,c) с обходом -> список полос; обход каждого треугольника сохраняется."""
    n = len(tris)
    if n == 0: return []
    edge = defaultdict(list)                                      # направленное ребро a->b -> треугольники
    for t, (a, b, c) in enumerate(tris):
        edge[(a, b)].append(t); edge[(b, c)].append(t); edge[(c, a)].append(t)
    used = np.zeros(n, bool)

    def third(t, a, b):                                           # треугольник t содержит ребро a->b: вернуть 3-ю
        x, y, z = tris[t]
        if (x, y) == (a, b): return z
        if (y, z) == (a, b): return x
        return y

    def nbr(t, a, b):                                             # следующий в полосе: ребро a->b в нужном направлении
        for u in edge[(a, b)]:
            if not used[u] and u != t: return u
        return -1

    def free_deg(t):
        a, b, c = tris[t]
        return sum(1 for e in ((b, a), (c, b), (a, c)) for u in edge[e] if not used[u] and u != t)

    order = sorted(range(n), key=free_deg)
    strips = []
    for t0 in order:
        if used[t0]: continue
        a, b, c = tris[t0]
        best = None
        for s in ((a, b, c), (b, c, a), (c, a, b)):               # с какого ребра продолжать
            used[t0] = True; seq = list(s); cur = t0; tr = [t0]
            while True:
                i = len(seq) - 2                                  # номер следующего треугольника в полосе
                e = (seq[-2], seq[-1]) if i % 2 == 0 else (seq[-1], seq[-2])
                # треугольник i полосы: чётный (s[-2],s[-1],x), нечётный (s[-1],s[-2],x) — ищем кусок с ребром e
                u = nbr(cur, e[0], e[1])
                if u < 0: break
                x = third(u, e[0], e[1])
                used[u] = True; tr.append(u); seq.append(x); cur = u
            for u in tr: used[u] = False
            if best is None or len(tr) > len(best[1]): best = (seq, tr)
        for u in best[1]: used[u] = True
        strips.append(best[0])
    return strips


def check_strip_winding(tris, seq):
    """проверка: каждый невырожденный треугольник полосы = исходный с тем же обходом."""
    want = {}
    for a, b, c in tris:
        k = min((a, b, c), (b, c, a), (c, a, b)); want[k] = want.get(k, 0) + 1
    got = {}
    for i in range(len(seq) - 2):
        a, b, c = seq[i], seq[i + 1], seq[i + 2]
        if a == b or b == c or a == c: continue
        if i % 2: a, b = b, a
        k = min((a, b, c), (b, c, a), (c, a, b)); got[k] = got.get(k, 0) + 1
    return want == got


def join(strips):
    out = []
    for s in strips:
        if out:
            if len(out) % 2 == 0: out += [out[-1], s[0]]          # s[0] встанет на чётную позицию
            else: out += [out[-1], s[0], s[0]]
        out += s
    return out


def first_use(seq):
    remap, order = {}, []
    for v in seq:
        if v not in remap: remap[v] = len(order); order.append(v)
    return np.array(order, np.int64), np.array([remap[v] for v in seq], np.int64)


# ---------------- растр вида: обход видимых треугольников ----------------
def matrices(eye, f):
    up = np.array([0.0, 1.0, 0.0])
    s = np.cross(f, up); s /= np.linalg.norm(s); u = np.cross(s, f)
    V = np.eye(4); V[0, :3], V[1, :3], V[2, :3] = s, u, -f; V[:3, 3] = -V[:3, :3] @ eye
    ct = 1 / math.tan(math.radians(FOVY) / 2); far = DRAW + 10
    P = np.zeros((4, 4)); P[0, 0] = ct / ASPECT; P[1, 1] = ct
    P[2, 2] = (far + ZNEAR) / (ZNEAR - far); P[2, 3] = 2 * far * ZNEAR / (ZNEAR - far); P[3, 2] = -1
    return P @ V


def raster(items, M, W=240, H=136, zb0=None, gid0=0):
    """items: [(piece_id, world_tris Nx3x3)] -> zbuf id (piece, tri) и знак площади каждого треугольника."""
    zb = np.full((H, W), np.inf) if zb0 is None else zb0.copy(); idb = np.full((H, W), -1, np.int64)
    gid = gid0; meta = []; orient = []; clipped = 0
    for pid, wt in items:
        n = len(wt)
        hom = np.concatenate([wt.reshape(-1, 3), np.ones((n * 3, 1))], 1) @ M.T
        hom = hom.reshape(n, 3, 4); w = hom[..., 3]
        ok = (w > ZNEAR * .999).all(1); clipped += int((~ok).sum())
        ndc = hom[..., :3] / np.where(np.abs(w) < 1e-9, 1e-9, w)[..., None]
        area = ((ndc[:, 1, 0] - ndc[:, 0, 0]) * (ndc[:, 2, 1] - ndc[:, 0, 1]) -
                (ndc[:, 2, 0] - ndc[:, 0, 0]) * (ndc[:, 1, 1] - ndc[:, 0, 1]))
        sx = (ndc[..., 0] + 1) * .5 * W; sy = (1 - ndc[..., 1]) * .5 * H; sz = ndc[..., 2]
        for t in range(n):
            if not ok[t]:                                          # режем ближней плоскостью (w = near), веером
                poly, P = [], hom[t]
                for j in range(3):
                    A, B = P[j], P[(j + 1) % 3]; ia, ib = A[3] > ZNEAR, B[3] > ZNEAR
                    if ia: poly.append(A)
                    if ia != ib: poly.append(A + (B - A) * ((ZNEAR - A[3]) / (B[3] - A[3])))
                meta.append((pid, t)); ar = 0.0
                if len(poly) >= 3:
                    q = np.array(poly); qn = q[:, :3] / q[:, 3:4]
                    ar = sum((qn[j, 0] - qn[0, 0]) * (qn[j + 1, 1] - qn[0, 1]) - (qn[j + 1, 0] - qn[0, 0]) * (qn[j, 1] - qn[0, 1])
                             for j in range(1, len(q) - 1))
                    for j in range(1, len(q) - 1):
                        tri = qn[[0, j, j + 1]]
                        _fill(zb, idb, gid, (tri[:, 0] + 1) * .5 * W, (1 - tri[:, 1]) * .5 * H, tri[:, 2], W, H)
                orient.append(ar); gid += 1; continue
            meta.append((pid, t)); orient.append(area[t])
            if abs(area[t]) < 1e-12: gid += 1; continue
            _fill(zb, idb, gid, sx[t], sy[t], sz[t], W, H); gid += 1
    return idb, meta, np.array(orient), clipped, zb


def _fill(zb, idb, gid, sx, sy, sz, W, H):
    if True:
        if True:
            x0 = max(int(math.floor(sx.min())), 0); x1 = min(int(math.ceil(sx.max())), W - 1)
            y0 = max(int(math.floor(sy.min())), 0); y1 = min(int(math.ceil(sy.max())), H - 1)
            if x0 > x1 or y0 > y1: return
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            (ax, bx, cx), (ay, by, cy) = sx, sy
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12: return
            l0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
            l1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
            l2 = 1 - l0 - l1
            ins = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            z = l0 * sz[0] + l1 * sz[1] + l2 * sz[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]; m = ins & (z < sub) & (z > -1.0001)
            sub[m] = z[m]; idb[y0:y1 + 1, x0:x1 + 1][m] = gid


# ---------------- текстуры (swizzle как в viewer/main.c) ----------------
def swizzle(data, w, h):
    hp = (h + 7) & ~7; rb = w // 16; out = bytearray(w * hp)
    for j in range(hp):
        row = data[min(j, h - 1) * w:(min(j, h - 1) + 1) * w]
        for bx in range(rb):
            o = ((j >> 3) * rb + bx) * 128 + (j & 7) * 16
            out[o:o + 16] = row[bx * 16:bx * 16 + 16]
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', default='build/level.shr'); ap.add_argument('--out', default='build/gebench/cell.bin')
    ap.add_argument('--view', nargs=3, type=float, default=[345, -81, 1])
    ap.add_argument('--lod', action='store_true', help='дальние куски (> 50 м) в дальней версии, как в движке; по умолчанию все ближние')
    a = ap.parse_args()
    L = read_level(a.level)
    car, eye, f = camera(L, a.view[0], a.view[1], int(a.view[2]))
    vis = cull(L, eye, f, a.lod)
    ntri = sum((len(L['pc'][k]['fidx']) if far else len(L['pc'][k]['idx'])) // 3 for k, far in vis)
    print(f'вид: машина {car[0]:.1f} {car[1]:.1f} {car[2]:.1f}, глаз {eye.round(2)}, кусков {len(vis)}, '
          f'треуг. {ntri} (ближних кусков {sum(1 for _, fr in vis if not fr)})')

    # --- наборы геометрии ---
    pieces = []
    for k, far in vis:
        p = L['pc'][k]; ix = (p['fidx'] if far else p['idx']).astype(np.int64)
        tris = ix.reshape(-1, 3)
        good = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])]
        pieces.append(dict(k=k, far=far, p=p, ix=ix, tris=[tuple(t) for t in good.tolist()]))

    # --- обход: какие видимые пиксели дают треугольники какого знака ---
    M = matrices(eye, f); items = []
    for pi, P in enumerate(pieces):
        v = P['p']['v']; pos = np.stack([v['x'], v['y'], v['z']], 1).astype(np.float64) / 32768.0 * P['p']['sc'] + np.array(P['p']['o'])
        items.append((pi, pos[np.array(P['tris'], np.int64).reshape(-1, 3)] if P['tris'] else np.zeros((0, 3, 3))))
    # непрозрачное закрывает; альфа-тест/полупрозрачное (заборы, решётки, листва) не закрывает — сквозь дырки видно
    opq = [it for it in items if not pieces[it[0]]['p']['flags'] & 3]
    alp = [it for it in items if pieces[it[0]]['p']['flags'] & 3]
    idb, meta, orient, clipped, zb = raster(opq, M)
    idb2, meta2, orient2, clipped2, _ = raster(alp, M, zb0=zb, gid0=len(meta))
    meta += meta2; orient = np.concatenate([orient, orient2]); clipped += clipped2
    cov = np.concatenate([idb[idb >= 0], idb2[idb2 >= 0]]); pix_ccw = defaultdict(int); pix_cw = defaultdict(int)
    for g, c in zip(*np.unique(cov, return_counts=True)):
        pid, t = meta[g]
        (pix_ccw if orient[g] > 0 else pix_cw)[pid] += int(c)
    tot_ccw, tot_cw = sum(pix_ccw.values()), sum(pix_cw.values())
    front_ccw = tot_ccw >= tot_cw                                    # «лицевой» обход = тот, что даёт больше видимых пикселей
    wrong_pix = tot_cw if front_ccw else tot_ccw
    # видимые треугольники с чужим обходом
    vis_g = set(int(g) for g in np.unique(cov))
    wrong_tris = sum(1 for g in vis_g if (orient[g] > 0) != front_ccw)
    flip, dbl = [], []
    for pi in range(len(pieces)):
        good, bad = (pix_ccw[pi], pix_cw[pi]) if front_ccw else (pix_cw[pi], pix_ccw[pi])
        if good + bad == 0: continue
        if bad > good: flip.append(pi); good, bad = bad, good
        if bad > .05 * (good + bad) and bad >= 4: dbl.append(pi)       # смешанный кусок: рисовать без отсечения
    resid = sum(min(pix_ccw[pi], pix_cw[pi]) for pi in range(len(pieces)) if pi not in dbl)
    wind = (f'обход (растр 240x136, покрыто {len(cov)} px, обрезано ближней плоскостью {clipped} треуг.): '
            f'лицевой = {"CCW" if front_ccw else "CW"} в экранных коорд. с y вверх; '
            f'с чужим обходом {wrong_pix} px = {100 * wrong_pix / max(1, len(cov)):.1f}% видимого, '
            f'{wrong_tris} из {len(vis_g)} видимых треуг.; по кускам: развернуть {len(flip)} из {len(pieces)}, '
            f'смешанных (без отсечения) {len(dbl)}, остаток после исправления {resid} px = {100 * resid / max(1, len(cov)):.1f}%')
    print(wind)

    sets = [[] for _ in range(5)]   # на кусок: (verts ndarray, idx ndarray|None, count)
    nstrip = ndeg = 0; bad_wind = 0
    for pi, P in enumerate(pieces):
        v = np.array(P['p']['v']); ix = P['ix']
        sets[0].append((v, ix, len(ix)))
        order, rix = first_use(ix.tolist()); sets[1].append((v[order], rix, len(rix)))
        for si, tr in ((2, P['tris']), (4, [(a, c, b) for a, b, c in P['tris']] if pi in flip else P['tris'])):
            st = stripify(tr); seq = join(st)
            if not check_strip_winding(tr, seq): bad_wind += 1
            if si == 2: nstrip += len(st); ndeg += len(seq) - 2 - len(tr)
            order, rix = first_use(seq)
            sets[si].append((v[order], rix, len(rix)))
            if si == 2: sets[3].append((v[np.array(seq, np.int64)] if seq else v[:0], None, len(seq)))
    if bad_wind: print(f'ВНИМАНИЕ: обход не сохранился в {bad_wind} полосах'); sys.exit(1)
    for si, nm in enumerate('ABCDF'):
        nv = sum(len(s[0]) for s in sets[si]); ni = sum(s[2] for s in sets[si])
        print(f'  набор {nm}: вершин {nv} ({nv * 16 / 1024:.0f} КБ), индексов/вершин в вызовах {ni}')
    print(f'  полос {nstrip}, вырожденных треуг. на склейках {ndeg}; вершин в вызове на треугольник: '
          f'список 3.00, полосы {sum(s[2] for s in sets[2]) / max(1, ntri):.2f}')

    # --- текстуры ---
    tex_ids = sorted({P['p']['tex'] for P in pieces if 0 <= P['p']['tex'] < L['ntex']})
    tmap = {t: i for i, t in enumerate(tex_ids)}

    # --- запись cell.bin ---
    NS = 5
    hdr_size, trec, prec = 128, 48, 32 + 16 * NS
    out = bytearray(hdr_size + trec * len(tex_ids) + prec * len(pieces)); out += b'\0' * (-len(out) % 16)

    def put(data):
        nonlocal out
        o = len(out); out += data; out += b'\0' * (-len(out) % 16); return o
    for i, t in enumerate(tex_ids):
        T = L['tex'][t]; po = put(T['pal']); lo = []
        for lw, lh, d in T['levels']: lo.append(put(swizzle(d, lw, lh)))
        struct.pack_into('<4HI8I', out, hdr_size + trec * i, T['w'], T['h'], len(T['levels']), 0, po, *(lo + [0] * (8 - len(lo))))
        struct.pack_into('<I', out, hdr_size + trec * i + 44, 0)
    setinfo = []
    recs = [[None] * NS for _ in pieces]
    for si in range(NS):
        vb0 = len(out)
        voff = []
        for s in sets[si]: voff.append(put(s[0].tobytes()))
        vb1 = len(out); ib0 = len(out); ioff = []
        for s in sets[si]: ioff.append(put(s[1].astype('<u2').tobytes()) if s[1] is not None else 0xFFFFFFFF)
        ib1 = len(out)
        setinfo += [vb0, vb1 - vb0, ib0, ib1 - ib0]
        for pi, s in enumerate(sets[si]): recs[pi][si] = (s[2], len(s[0]), voff[pi], ioff[pi])
    for pi, P in enumerate(pieces):
        p = P['p']; o = hdr_size + trec * len(tex_ids) + prec * pi
        struct.pack_into('<4i4f', out, o, tmap.get(p['tex'], -1), p['flags'], 1 if pi in dbl else 0, 1 if P['far'] else 0, p['sc'], *p['o'])
        for si in range(NS): struct.pack_into('<4I', out, o + 32 + 16 * si, *recs[pi][si])
    at = eye + f
    struct.pack_into('<4s3I3f3fII', out, 0, b'GEB1', len(tex_ids), len(pieces), NS, *eye, *at, 0xe0b070, 1 if front_ccw else 0)
    struct.pack_into(f'<{4 * NS}I', out, 48, *setinfo)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'wb').write(out)
    with open(os.path.join(os.path.dirname(a.out), 'cell_info.txt'), 'w') as fo:
        fo.write(f'view {a.view} car {car} eye {eye.tolist()} pieces {len(pieces)} tris {ntri} tex {len(tex_ids)}\n{wind}\n')
    print(f'{a.out}: {len(out) / 1024:.0f} КБ, текстур {len(tex_ids)}')


if __name__ == '__main__':
    main()
