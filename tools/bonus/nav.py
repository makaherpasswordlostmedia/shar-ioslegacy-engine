"""Путь ИИ по трассе мини-игры между точками WPR/WPL (ПРАВИЛО ПОРТА, правка 420).

У оригинала на трассе 4–9 точек пути на круг; между ними дорога поворачивает (b01: от WPR05 у восточной петли до WPR01 в
середине — разворот), прямая к следующей точке упирается в бортик: полигон tools/bonus/race_host.c это показал (соперники
застревали у старта). Как оригинал ведёт машину между точками — в данных нет (вопрос в knowledge/questions.tsv). Порт
прокладывает путь по опоре трассы: сетка 1 м по проходимым треугольникам COL1 этой же трассы (n.y > 0.5 — col.h COL_WALK_NY),
несколько ярусов в одной клетке (мосты, развязки), соседи связаны, если перепад ≤ STEP (ступенька машины car.c 0.35 м);
вертикальные треугольники перекрывают ярус по своей высоте. Цена шага растёт у края (держаться середины полотна).
Кратчайший путь (Дейкстра) от точки к точке, прореживание через PATH_STEP м, сглаживание."""
import heapq, math, os, struct
import numpy as np

G = 1.0          # шаг сетки, м
STEP = 0.35      # car.c CarParams.step: на какую ступеньку можно въехать
WALL_LO, WALL_HI = 0.3, 1.6   # слой кузова car.c bandLo..bandHi: стена в нём перекрывает ярус
EDGE_K = 6.0     # цена близости к краю (правило порта): шаг = 1 + EDGE_K / (зазор + 1)
PATH_STEP = 4.0  # м между точками пути
CLR_MIN = 2.0    # м: узлы ближе к краю опоры не берутся в путь (машина шире 2 м; правило порта), кроме начала и конца


def col_tris(shr):
    b = open(shr, 'rb').read()
    co = struct.unpack_from('<I', b, 92)[0]
    assert b[co:co + 4] == b'COL1'
    ox, oz, cell = struct.unpack_from('<3f', b, co + 4); W, H, ntri = struct.unpack_from('<3I', b, co + 16)
    return np.frombuffer(b, '<f4', ntri * 12, co + 48).reshape(-1, 4, 3).astype(np.float64)


class Nav:
    def __init__(self, tris):
        P = tris[:, :3]; N = tris[:, 3]
        walk = N[:, 1] > 0.5
        lo = P.reshape(-1, 3).min(0); hi = P.reshape(-1, 3).max(0)
        self.ox, self.oz = math.floor(lo[0]) - 2, math.floor(lo[2]) - 2
        self.W = int((hi[0] - self.ox) / G) + 4; self.H = int((hi[2] - self.oz) / G) + 4
        hs = [[] for _ in range(self.W * self.H)]
        for t in P[walk]:
            a, b, c = t
            x0, x1 = int((min(a[0], b[0], c[0]) - self.ox) / G), int((max(a[0], b[0], c[0]) - self.ox) / G) + 1
            z0, z1 = int((min(a[2], b[2], c[2]) - self.oz) / G), int((max(a[2], b[2], c[2]) - self.oz) / G) + 1
            xs, zs = np.meshgrid(self.ox + (np.arange(x0, x1 + 1) + .5) * G, self.oz + (np.arange(z0, z1 + 1) + .5) * G)
            d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            if abs(d) < 1e-9: continue
            l1 = ((b[2] - c[2]) * (xs - c[0]) + (c[0] - b[0]) * (zs - c[2])) / d
            l2 = ((c[2] - a[2]) * (xs - c[0]) + (a[0] - c[0]) * (zs - c[2])) / d
            l3 = 1 - l1 - l2; m = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            ys = l1 * a[1] + l2 * b[1] + l3 * c[1]
            for x, z, y in zip(xs[m], zs[m], ys[m]):
                i, j = int((x - self.ox) / G), int((z - self.oz) / G); hs[j * self.W + i].append(float(y))
        self.layers = []   # на клетку — список высот ярусов
        for h in hs:
            h.sort(); L = []
            for y in h:
                if L and y - L[-1] < 0.3: L[-1] = max(L[-1], y)   # одна опора (верх)
                else: L.append(y)
            self.layers.append(L)
        # стены: вертикальные треугольники перекрывают ярус, если входят в слой кузова над ним
        self.block = [set() for _ in range(self.W * self.H)]
        for t in P[~walk]:
            ymin, ymax = t[:, 1].min(), t[:, 1].max()
            pts = []
            for u, v in ((0, 1), (1, 2), (2, 0)):
                L_ = math.hypot(t[v][0] - t[u][0], t[v][2] - t[u][2]); k = max(1, int(L_ / (G * .5)))
                for s in range(k + 1): pts.append(t[u] + (t[v] - t[u]) * s / k)
            for p in pts:
                i, j = int((p[0] - self.ox) / G), int((p[2] - self.oz) / G)
                if not (0 <= i < self.W and 0 <= j < self.H): continue
                c = j * self.W + i
                for k_, y in enumerate(self.layers[c]):
                    if ymax > y + WALL_LO and ymin < y + WALL_HI: self.block[c].add(k_)
        self.ids = {}; self.nodes = []
        for c, L in enumerate(self.layers):
            for k_ in range(len(L)):
                if k_ in self.block[c]: continue
                self.ids[(c, k_)] = len(self.nodes); self.nodes.append((c, k_))
        self.adj = [[] for _ in self.nodes]
        for n, (c, k_) in enumerate(self.nodes):
            i, j = c % self.W, c // self.W; y = self.layers[c][k_]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                ii, jj = i + di, j + dj
                if not (0 <= ii < self.W and 0 <= jj < self.H): continue
                c2 = jj * self.W + ii; best = None
                for k2, y2 in enumerate(self.layers[c2]):
                    if (c2, k2) in self.ids and abs(y2 - y) <= STEP and (best is None or abs(y2 - y) < abs(self.layers[c2][best] - y)): best = k2
                if best is not None: self.adj[n].append((self.ids[(c2, best)], math.hypot(di, dj)))
        # зазор до края: волна от узлов, у которых меньше 8 соседей
        INF = 1e9; self.clear = [INF] * len(self.nodes); q = []
        for n, a in enumerate(self.adj):
            if len(a) < 8: self.clear[n] = 0.0; q.append(n)
        h = 0
        while h < len(q):
            n = q[h]; h += 1
            for m, w in self.adj[n]:
                if self.clear[m] > self.clear[n] + w: self.clear[m] = self.clear[n] + w; q.append(m)

    def node_at(self, p, prefer_y=None):
        i, j = int((p[0] - self.ox) / G), int((p[2] - self.oz) / G)
        best = None
        for r in range(0, 6):   # ближняя клетка с ярусом
            for jj in range(j - r, j + r + 1):
                for ii in range(i - r, i + r + 1):
                    if not (0 <= ii < self.W and 0 <= jj < self.H): continue
                    c = jj * self.W + ii
                    for k_, y in enumerate(self.layers[c]):
                        if (c, k_) not in self.ids: continue
                        d = (ii - i) ** 2 + (jj - j) ** 2 + 4 * (y - (prefer_y if prefer_y is not None else p[1])) ** 2
                        if best is None or d < best[0]: best = (d, self.ids[(c, k_)])
            if best: return best[1]
        return None

    def pos(self, n):
        c, k_ = self.nodes[n]; return (self.ox + (c % self.W + .5) * G, self.layers[c][k_], self.oz + (c // self.W + .5) * G)

    def route(self, a, b):
        """кратчайший путь узлов a -> b (цена: длина × (1 + EDGE_K / (зазор + 1))); узкие места (зазор < CLR_MIN) — только
        если иначе не проехать"""
        for self.clr_min in (CLR_MIN, 0.0):
            r = self._route(a, b)
            if r is not None: return r
        return None

    def _route(self, a, b):
        dist = {a: 0.0}; prev = {}; pq = [(0.0, a)]
        while pq:
            d, n = heapq.heappop(pq)
            if n == b: break
            if d > dist.get(n, 1e18): continue
            for m, w in self.adj[n]:
                if self.clear[m] < self.clr_min and m != b: continue
                nd = d + w * (1 + EDGE_K / (self.clear[m] + 1))
                if nd < dist.get(m, 1e18): dist[m] = nd; prev[m] = n; heapq.heappush(pq, (nd, m))
        if b not in dist: return None
        out = [b]
        while out[-1] != a: out.append(prev[out[-1]])
        return [self.pos(n) for n in reversed(out)]


def resample(pts, step=PATH_STEP):
    pts = [np.array(p, float) for p in pts]
    out = [pts[0]]; acc = 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[2] - a[2])
        while acc + L >= step and L > 1e-9:
            t = (step - acc) / L; a = a + (b - a) * t; out.append(a); L = math.hypot(b[0] - a[0], b[2] - a[2]); acc = 0.0
        acc += L
    return out


def smooth(pts, it=3):
    P = np.array(pts, float)
    for _ in range(it):
        Q = P.copy(); Q[1:-1] = (P[:-2] + 2 * P[1:-1] + P[2:]) / 4; P = Q
    return P


def _d(a, b): return math.hypot(a[0] - b[0], a[2] - b[2])


def insert_via(stops, wps, max_detour=1.5):
    """точки пути данных -> {номер отрезка остановок: [точки по ходу]}: каждая — в отрезок (stops[i-1] -> stops[i], по кругу) с
    наименьшим крюком; крюк больше max_detour длины отрезка — точка не берётся (правило порта)"""
    via = {}
    for w in wps:
        best = None
        for i in range(len(stops)):
            a, b = stops[i - 1], stops[i]; L = _d(a, b) + 1e-6; det = (_d(a, w) + _d(w, b) - L) / L
            if best is None or det < best[0]: best = (det, i)
        if best and best[0] <= max_detour: via.setdefault(best[1], []).append(w)
    for i, ws in via.items():
        a = stops[i - 1]; ws.sort(key=lambda w: _d(a, w))
    return via


def inside(cp, p, grow=0.0):
    t = cp['trig'][0]; d = [p[k] - t['c'][k] for k in range(3)]
    if not t['rect']: return sum(x * x for x in d) <= (t['h'][0] + grow) ** 2
    return all(abs(sum(d[k] * t['axes'][a][k] for k in range(3))) <= t['h'][a] + grow for a in range(3))


def stop_points(nav, cps):
    """остановка у чекпойнта — точка опоры внутри его объёма, ближе всего к прямой между соседями (правило порта: центр объёма
    бывает в стороне от полотна — b07 check5 вытянут вдоль дороги, его центр — на краю; путь к центру давал петлю)"""
    out = []
    for i, c in enumerate(cps):
        a, b = cps[i - 1]['pos'], cps[(i + 1) % len(cps)]['pos']
        t = c['trig'][0]; R = max(t['h']) + 1
        best = None
        for n, (cell, k) in enumerate(nav.nodes):
            x, y, z = nav.pos(n)
            if abs(x - t['c'][0]) > R or abs(z - t['c'][2]) > R or not inside(c, (x, y + 0.5, z)): continue
            if nav.clear[n] < 2.0: continue   # не у самого края
            cost = _d(a, (x, y, z)) + _d((x, y, z), b)
            if best is None or cost < best[0]: best = (cost, (x, y, z))
        out.append(best[1] if best else tuple(c['pos']))
    return out


def loop_path(nav, stops, via=None):
    """stops — остановки круга по порядку (последняя — финиш), путь замкнут; via — промежуточные точки отрезков (insert_via).
    -> (точки [x,y,z], номер остановки у точки (-1 — промежуточная)); путь отрезка i ведёт к stops[i] (от stops[i-1])"""
    pts, tag = [], []
    via = via or {}
    for i in range(len(stops)):
        chain = [stops[i - 1]] + via.get(i, []) + [stops[i]]
        r = []
        for s, e in zip(chain, chain[1:]):
            a, b = nav.node_at(s), nav.node_at(e)
            q = nav.route(a, b) if a is not None and b is not None else None
            if q is None: q = [s, e]   # не связаны по опоре — прямая (как раньше), полигон покажет
            r += q if not r else q[1:]
        seg = smooth(resample(r)) if len(r) > 2 else np.array(r, float)
        seg = list(seg[1:])        # начало — конец прошлого отрезка (остановка i-1)
        pts += [list(map(float, p)) for p in seg]; tag += [-1] * (len(seg) - 1) + [i]
    return despike(pts, tag) if os.environ.get('BONUS_DESPIKE') == '1' else (pts, tag)   # WIP 09.10: срез шпилек — для водителя трассы


def despike(pts, tag, close=3.0, arc_min=12.0, look=20):
    """срез «туда и обратно»: путь уходит и возвращается почти в ту же точку (ближе close м по xz и по высоте) через дугу длиннее
    arc_min м без остановок внутри — дугу убрать (правило порта: промежуточная точка WPR в тупике давала шпильку, 09.10 b02)"""
    i = 0
    while i < len(pts):
        n = len(pts); cut = None
        for j in range(i + 3, min(i + look, n)):
            if any(t >= 0 for t in tag[i + 1:j]): break
            a, b = pts[i], pts[j]
            if math.hypot(a[0] - b[0], a[2] - b[2]) < close and abs(a[1] - b[1]) < 1.5:
                arc = sum(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][2] - pts[k][2]) for k in range(i, j))
                if arc > arc_min: cut = j
        if cut: del pts[i + 1:cut]; del tag[i + 1:cut]
        i += 1
    return pts, tag
