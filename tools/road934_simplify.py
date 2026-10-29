"""Упрощение сетки дороги с границей ошибки (№934): схлопывание рёбер по квадрикам Гарланда–Хекберта, но
  - вершина встаёт только в уже существующую (u -> v или v -> u): новых точек нет, край не «плывёт»;
  - границе сетки (ребро с одним треугольником: край дороги и пролёта) добавлена плоскость-ограничитель с весом BW: сдвиг края стоит дорого;
  - граничная вершина идёт только по граничному ребру (в середину полотна не уходит), нет складки: нормаль соседнего треугольника не разворачивается (> COS_MIN) и не вырождается;
  - стоп: наименьшая цена (сумма квадратов расстояний до плоскостей рядом) больше eps².
fast-simplification для этого не годится: у него нет границы ошибки, край дороги сжимается (охват масок 0,92–0,96 на 270–500 м).
Только numpy и стандартная библиотека. simplify(pts (N,3), F (M,3), eps, bw) -> (pts2, F2)"""
import heapq
import numpy as np

COS_MIN = 0.35


def _plane(p0, p1, p2):
    n = np.cross(p1 - p0, p2 - p0); l = np.linalg.norm(n)
    if l < 1e-12: return None
    n = n / l
    return np.array([n[0], n[1], n[2], -float(n @ p0)])


def simplify(pts, F, eps=0.35, bw=40.0, max_collapses=10 ** 9):
    P = np.asarray(pts, np.float64); F = np.asarray(F, np.int64)
    n = len(P); faces = [tuple(int(x) for x in f) for f in F]; alive = [True] * len(faces)
    vf = [set() for _ in range(n)]
    for i, f in enumerate(faces):
        for v in f: vf[v].add(i)
    Q = np.zeros((n, 4, 4))
    edge_faces = {}
    for i, f in enumerate(faces):
        pl = _plane(P[f[0]], P[f[1]], P[f[2]])
        if pl is not None:
            K = np.outer(pl, pl)
            for v in f: Q[v] += K
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(i)
    bnd = np.zeros(n, bool)
    for (a, b), fl in edge_faces.items():
        if len(fl) != 1: continue
        f = faces[fl[0]]; pl = _plane(P[f[0]], P[f[1]], P[f[2]])
        if pl is None: continue
        e = P[b] - P[a]; el = np.linalg.norm(e)
        if el < 1e-9: continue
        c = np.cross(e / el, pl[:3]); cl = np.linalg.norm(c)
        if cl < 1e-9: continue
        c = c / cl; bp = np.array([c[0], c[1], c[2], -float(c @ P[a])]); K = bw * np.outer(bp, bp)
        Q[a] += K; Q[b] += K; bnd[a] = bnd[b] = True
    bedge = {e for e, fl in edge_faces.items() if len(fl) == 1}
    ver = [0] * n

    def nbrs(v):
        s = set()
        for fi in vf[v]:
            for w in faces[fi]:
                if w != v: s.add(w)
        return s

    def cost(u, v):   # u -> v
        pv = np.append(P[v], 1.0)
        return float(pv @ (Q[u] + Q[v]) @ pv)

    def legal(u, v):
        if bnd[u] and (not bnd[v] or (min(u, v), max(u, v)) not in bedge): return False
        shared = vf[u] & vf[v]
        if not shared: return False
        cn = nbrs(u) & nbrs(v)
        if len(cn) != len(shared): return False   # условие связности: общих соседей ровно столько, сколько общих граней
        for fi in vf[u] - shared:
            f = faces[fi]; a, b, c = f
            old = np.cross(P[b] - P[a], P[c] - P[a])
            g = [v if x == u else x for x in f]
            new = np.cross(P[g[1]] - P[g[0]], P[g[2]] - P[g[0]])
            lo, ln = np.linalg.norm(old), np.linalg.norm(new)
            if ln < 1e-9 or lo < 1e-12: return False
            if float(old @ new) / (lo * ln) < COS_MIN: return False
            if ln < 0.02 * lo: return False
        return True

    heap = []
    def push(u, v):
        heapq.heappush(heap, (cost(u, v), u, v, ver[u], ver[v]))
    for (a, b) in edge_faces:
        push(a, b); push(b, a)
    e2 = eps * eps; done = 0
    while heap and done < max_collapses:
        c, u, v, vu, vv = heapq.heappop(heap)
        if c > e2: break
        if ver[u] != vu or ver[v] != vv or not (vf[u] and vf[v]): continue
        if not legal(u, v): continue
        # схлопываем u -> v
        shared = vf[u] & vf[v]
        for fi in shared:
            alive[fi] = False
            for w in faces[fi]: vf[w].discard(fi)
        for fi in list(vf[u]):
            faces[fi] = tuple(v if x == u else x for x in faces[fi]); vf[v].add(fi)
        vf[u] = set(); Q[v] += Q[u]; bnd[v] = bnd[v] or bnd[u]; ver[u] += 1; ver[v] += 1
        # граничные рёбра: переименовать u в v
        for e in [e for e in bedge if u in e]:
            bedge.discard(e); w = e[0] if e[1] == u else e[1]
            if w != v: bedge.add((min(w, v), max(w, v)))
        for w in nbrs(v): push(v, w); push(w, v)
        done += 1
    keep = [f for f, a in zip(faces, alive) if a and len(set(f)) == 3]
    used = sorted({x for f in keep for x in f}); remap = {o: i for i, o in enumerate(used)}
    F2 = np.array([[remap[x] for x in f] for f in keep], np.int32).reshape(-1, 3)
    return P[used].astype(np.float32), F2
