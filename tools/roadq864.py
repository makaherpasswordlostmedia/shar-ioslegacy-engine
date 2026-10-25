#!/usr/bin/env python3
# №864 (окно «Оптимизация»), пропечка 2: «загрузка вдоль дороги» (как у Crash Bandicoot: кто едет по дороге, тот на 2-3 с вперёд уже знает, какие куски уровня ему понадобятся).
# Дорожный граф traffic.shr (TRF1: перекрёстки, односторонние дороги с полосами) + клетки level.shr -> roadq-l<N>.bin рядом с уровнем (RQ1).
# Для каждой клетки и каждого из 8 направлений хода (0 = +Z, дальше по 45 градусов в сторону +X; как в движке: atan2(dx, dz)) — до RQ_M клеток впереди по дороге в пределах RQ_AHEAD м, ближние первыми.
#   python3 tools/roadq864.py LEVEL.shr TRAFFIC.shr OUT.bin [--stats]
# Формат RQ1 (little endian): 'RQ1\0', u32 ncell, u32 nb(=8), u32 total; u32 off[ncell*nb+1]; u16 cells[total]
import sys, struct, math, numpy as np
RQ_AHEAD = 260.0   # м вперёд по дороге (2-3 с на скорости 90-100 км/ч)
RQ_M = 14          # клеток на (клетка, направление)
RQ_STEP = 8.0      # шаг выборки вдоль дороги, м
NB = 8

def load_cells(path):
    with open(path, 'rb') as f:
        h = f.read(104)
        ncell, cellOff = struct.unpack_from('<II', h, 80)
        f.seek(cellOff); b = f.read(48 * ncell)
    a = np.frombuffer(b, dtype=np.uint8).reshape(ncell, 48)
    bb = a[:, :24].copy().view('<f4').reshape(ncell, 6)
    owner = a[:, 24:48].copy().view('<u4').reshape(ncell, 6)[:, 2]
    return bb, owner

def load_roads(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'TRF1'
    u = struct.unpack_from('<20I', d, 8)
    nJ, offJ, nR, offR, nP, offP = u[2], u[3], u[4], u[5], u[6], u[7]
    # TrHeader: magic, version, size, nJunc, offJunc, nRoad, offRoad, nPt, offPt, ...
    nJ, offJ, nR, offR, nP, offP = struct.unpack_from('<6I', d, 12)
    junc = [struct.unpack_from('<4fIHHHHI', d, offJ + 32 * i) for i in range(nJ)]
    roads = []
    for i in range(nR):
        sj, ej, rev, lanes, fl, mc, sp, _p8, fp, npt, _p16, length, width, _p = struct.unpack_from('<4H4BIHHfff', d, offR + 32 * i)
        pts = np.frombuffer(d, dtype='<f4', count=4 * nP, offset=offP).reshape(nP, 4)
        roads.append(dict(sj=sj, ej=ej, rev=rev, lanes=max(lanes, 1), flags=fl, fp=fp, npt=npt, length=length, pts=pts[fp:fp + npt]))
    return junc, roads

def densify(p, step):
    # ломаная [(x,y,z)], шаг step; возвращает массив точек и расстояний от начала
    out = [p[0]]; dist = [0.0]; acc = 0.0
    for i in range(1, len(p)):
        a, b = p[i - 1], p[i]; seg = float(np.linalg.norm(b - a))
        if seg < 1e-3: continue
        n = max(1, int(math.ceil(seg / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * (k / n)); dist.append(acc + seg * k / n)
        acc += seg
    return np.array(out), np.array(dist)

class Grid:
    def __init__(s, bb, g=48.0):
        s.g = g; s.bb = bb; s.h = {}
        for i, b in enumerate(bb):
            for gx in range(int(math.floor(b[0] / g)), int(math.floor(b[3] / g)) + 1):
                for gz in range(int(math.floor(b[2] / g)), int(math.floor(b[5] / g)) + 1):
                    s.h.setdefault((gx, gz), []).append(i)
    def at(s, x, y, z):
        r = []
        for i in s.h.get((int(math.floor(x / s.g)), int(math.floor(z / s.g))), ()):
            b = s.bb[i]
            if b[0] <= x <= b[3] and b[2] <= z <= b[5] and b[1] - 6.0 <= y <= b[4] + 6.0: r.append(i)
        return r

def bake(lvl, trf, stats=False):
    bb, owner = load_cells(lvl); ncell = len(bb)
    junc, roads = load_roads(trf)
    grid = Grid(bb)
    out_of = {}
    for i, r in enumerate(roads):
        out_of.setdefault(r['sj'], []).append(i)
    dens = []
    for r in roads:
        if r['npt'] < 2: dens.append((np.zeros((0, 3)), np.zeros(0))); continue
        dens.append(densify(r['pts'][:, :3].astype(np.float64), RQ_STEP))
    best = [dict() for _ in range(ncell * NB)]   # (cell*NB+bucket) -> {target: min s}
    def walk(road, start, budget, acc, seen, hits):
        # точки дороги road с индекса start; budget — сколько метров ещё; acc — пройдено от источника
        P, D = dens[road]
        if len(P) == 0: return
        base = D[start] if start < len(D) else 0.0
        j = start
        while j < len(P):
            s = acc + (D[j] - base)
            if s > RQ_AHEAD: return
            for c in grid.at(*P[j]): hits.append((c, s))
            j += 1
        # конец дороги: выезды с перекрёстка (кроме разворота обратно по rev), глубина до 3 развилок
        tail = acc + (D[-1] - base)
        if len(seen) >= 4: return
        for nr in out_of.get(roads[road]['ej'], ()):
            if nr == roads[road]['rev'] or nr in seen: continue
            walk(nr, 0, budget, tail, seen + [nr], hits)
    for ri, r in enumerate(roads):
        P, D = dens[ri]
        if len(P) < 2: continue
        for j in range(0, len(P) - 1):
            t = P[min(j + 3, len(P) - 1)] - P[j]
            if t[0] * t[0] + t[2] * t[2] < 1e-6: continue
            ang = math.atan2(t[0], t[2]); b = int(round(ang / (math.pi / 4))) % NB
            src = grid.at(*P[j])
            if not src: continue
            hits = []
            walk(ri, j, RQ_AHEAD, 0.0, [ri], hits)
            mins = {}
            for c, s in hits:
                if c not in mins or s < mins[c]: mins[c] = s
            for i in src:
                d = best[i * NB + b]
                for c, s in mins.items():
                    if c == i: continue
                    if c not in d or s < d[c]: d[c] = s
    off = [0]; ents = []
    for k in range(ncell * NB):
        lst = sorted(best[k].items(), key=lambda kv: kv[1])[:RQ_M]
        ents.extend(c for c, _ in lst); off.append(len(ents))
    blob = b'RQ1\0' + struct.pack('<III', ncell, NB, len(ents)) + np.array(off, dtype='<u4').tobytes() + np.array(ents, dtype='<u2').tobytes()
    if stats:
        ne = sum(1 for k in range(ncell * NB) if off[k + 1] > off[k])
        print(f'RQSTAT ncell={ncell} roads={len(roads)} lists={ne}/{ncell * NB} entries={len(ents)} bytes={len(blob)}')
    return blob

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) != 3: sys.exit(__doc__)
    blob = bake(a[0], a[1], '--stats' in sys.argv)
    open(a[2], 'wb').write(blob)
