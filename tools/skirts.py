"""Юбки швов (правка Роба 106, повтор 01.10: «сделай наслоение друг на друга, чтобы не было стыков между полигонами»;
«не допускай, чтобы пересборка опять возвращала швы»). Правило порта, одно для всех уровней и обеих версий куска.

Где шов. Кусок города рисуется ближней версией ближе LOD_DIST 50 м и дальней дальше (viewer/main.c). Край куска закрыт,
если у соседнего куска той же версии есть то же ребро (вершины на общей решётке, правка 37: бит в бит). Открытый край —
щель в данных: в дальней версии выкинута мелочь мельче FAR_MIN (бордюр, кромка — tools/psp_export.py far_keep оставляет
лишь 15 %), Т-стык исходных треугольников, мелкий разнобой мешей художников. Сквозь щель на PSP видно небо: оно рисуется
последним в пустую глубину (O_SKYLAST) — голубая полоса вдоль бордюра или стыка на асфальте, «рябит» при движении.

Правило «юбки». Открытый край треугольника земли (наклон до 60°), за которым в PROBE = 2 см лежит земля — на той же
высоте (±SKIRT_TOL) или ниже не больше SKIRT_DROP (выкинутая грань бордюра), — получает юбку, цвет и UV — края
(растянутый крайний тексель):
  * земля за краем ниже (ступенька, бордюр без грани) — вертикальная полоса вниз до той земли плюс SKIRT_DEPTH: на месте
    выкинутой грани встаёт грань того же цвета;
  * земля за краем на той же высоте (щель в плоскости: выкинутая полоса, Т-стык) — полоса наружу-вниз под землю соседа
    (REACH_OUT наружу, REACH_DOWN вниз): от двух краёв щели — жёлоб «V», который ловит и луч вдоль щели (вертикальная
    юбка его пропустила бы: луч вдоль бордюра опускается между стенками и уходит под них); край соседа лежит над ней.
Луч камеры, прошедший щель, падает на юбку: щель закрыта цветом той же поверхности. Сверху юбку не видно (под краем и
под землёй соседа), коллизии у неё нет (коллизия — отдельная секция COL1), вид сверху не меняется. Закрытые края (есть ребро-близнец у соседа) юбку не
получают: в данных там щели нет, а лишняя полоса стоила бы треугольников GE. Цепочки краёв по прямой — одной полосой-веером (верх по всем вершинам края: без Т-стыка).
Где за краем нет земли (обрыв, край крыши, стена вверх) — юбки нет. Слои (64), альфа-тест, полупрозрачное, небо — без юбок.

Замер и сторож — tools/seams_raster.py (швы кадра PSP на 22 видах, --gate в tools/ship.sh); тест — tests/seams/skirts.py."""
import numpy as np

SKIRT_DEPTH = 0.06   # м: наслоение — юбка уходит ниже земли за краем
SKIRT_TOL = 0.05     # м: земля за краем выше края не больше (та же поверхность)
SKIRT_DROP = 0.5     # м: ...и ниже не больше (выкинутая грань бордюра, ступенька); глубже — обрыв, юбки нет
PROBE = 0.02         # м: пробная точка за краем, наружу от треугольника
GROUND_NY = 0.5      # |n.y| > 0.5 — земля (наклон до 60°)
CELL = 4.0           # м: решётка поиска земли
REACH_OUT = 0.25    # м: юбка щели в плоскости — наружу (закрывает щель до 2·REACH_OUT от двух краёв, до REACH_OUT от одного)
REACH_DOWN = 0.35   # м: ...и вниз (круче 45°: под землёй соседа, не над ней)
CHAIN_DEV = 0.002    # м: края юбок склеиваются в одну полосу, если ломаная отходит от прямой не больше
XCELL_MINLEN = float(__import__('os').environ.get('SHR_XCELL_MINLEN', 3.0))   # м
Q = 8192.0           # решётка города 2^-9 м — целые в 1/8192 м без потерь (ключи рёбер)


def ground_mask(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    return np.abs(n[:, 1]) > GROUND_NY * np.maximum(np.linalg.norm(n, axis=1), 1e-12)


def edge_keys(T):
    """ключи рёбер (n,3) треугольников: (меньшая вершина, большая) на решётке -> (3n, 6) int64; ребро k треугольника t —
    строка k·n + t"""
    q = np.round(np.asarray(T, np.float64).reshape(-1, 3, 3) * Q).astype(np.int64)
    a = np.concatenate([q[:, 0], q[:, 1], q[:, 2]]); b = np.concatenate([q[:, 1], q[:, 2], q[:, 0]])
    less = (a[:, 0] < b[:, 0]) | ((a[:, 0] == b[:, 0]) & ((a[:, 1] < b[:, 1]) | ((a[:, 1] == b[:, 1]) & (a[:, 2] < b[:, 2]))))
    return np.c_[np.where(less[:, None], a, b), np.where(less[:, None], b, a)]


def _hash(K):
    h = np.zeros(len(K), np.uint64)
    with np.errstate(over='ignore'):
        for j in range(6): h = h * np.uint64(1_000_003) + K[:, j].astype(np.uint64)
    return h


class EdgeOwners:
    """рёбра всех кусков одной версии: у кого ещё есть это ребро (близнец у соседа = край закрыт)"""

    def __init__(self, tri_sets, cells=None, texs=None):
        self.cells = None if cells is None else np.asarray(cells, np.int64)
        self.texs = None if texs is None else np.asarray(texs, np.int64)   # текстура куска: край общий с другой текстурой (бордюр/газон/асфальт)
        K, O = [], []
        for own, T in tri_sets:
            if len(T): k = np.unique(edge_keys(T), axis=0); K.append(k); O.append(np.full(len(k), own, np.int64))
        self.K = np.concatenate(K) if K else np.zeros((0, 6), np.int64)
        self.O = np.concatenate(O) if O else np.zeros(0, np.int64)
        self.h = _hash(self.K); o = np.argsort(self.h, kind='stable'); self.h, self.K, self.O = self.h[o], self.K[o], self.O[o]

    def twin(self, K, own):
        """K (m,6) ключи рёбер куска own -> маска: то же ребро есть у другого куска"""
        out = np.zeros(len(K), bool)
        if not len(K) or not len(self.K): return out
        h = _hash(K); s, e = np.searchsorted(self.h, h, 'left'), np.searchsorted(self.h, h, 'right'); m = e - s
        qi = np.repeat(np.arange(len(K)), m); ci = np.repeat(s, m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))
        hit = (self.K[ci] == K[qi]).all(1) & (self.O[ci] != own)
        out[qi[hit]] = True
        return out

    def twin_xcell(self, K, own):
        """K (m,6) -> маска: ребро есть у куска ДРУГОЙ клетки 40 м и ни у одного куска своей (правка 507: у клеток разные матрицы GE,
        общее ребро округляется по-разному — щель в 1/16 пикселя, которую «закрытый» край не страхует)"""
        out = np.zeros(len(K), bool)
        if self.cells is None or not len(K) or not len(self.K): return out
        h = _hash(K); s, e = np.searchsorted(self.h, h, 'left'), np.searchsorted(self.h, h, 'right'); m = e - s
        qi = np.repeat(np.arange(len(K)), m); ci = np.repeat(s, m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))
        same = (self.K[ci] == K[qi]).all(1) & (self.O[ci] != own)
        other = same & (self.cells[self.O[ci]] != self.cells[own])
        if self.texs is not None: other &= self.texs[self.O[ci]] != self.texs[own]   # только стык РАЗНЫХ текстур
        mine = same & (self.cells[self.O[ci]] == self.cells[own])
        o_any = np.zeros(len(K), bool); o_any[qi[other]] = True; m_any = np.zeros(len(K), bool); m_any[qi[mine]] = True
        return o_any & ~m_any


class GroundIndex:
    """земля всего города (ближние версии непрозрачных кусков) в решётке XZ: высота земли под точкой в окне высот"""

    def __init__(self, T):
        T = np.asarray(T, np.float64).reshape(-1, 3, 3)
        self.T = T[ground_mask(T)]
        lo = np.floor(self.T[:, :, [0, 2]].min(1) / CELL).astype(np.int64)
        hi = np.floor(self.T[:, :, [0, 2]].max(1) / CELL).astype(np.int64)
        sp = hi - lo + 1; cnt = sp[:, 0] * sp[:, 1]
        rep = np.repeat(np.arange(len(self.T)), cnt); k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        key = self._key(lo[rep, 0] + k % sp[rep, 0], lo[rep, 1] + k // sp[rep, 0])
        o = np.argsort(key, kind='stable'); self.key, self.tri = key[o], rep[o]

    @staticmethod
    def _key(gx, gz): return (gx + 1_000_000) * 2_000_003 + (gz + 1_000_000)

    def top(self, P, up=SKIRT_TOL, down=SKIRT_DROP):
        """P (k,3) точки -> высота самой верхней земли под точкой в окне [y - down, y + up] (NaN — нет)"""
        out = np.full(len(P), np.nan)
        if not len(P) or not len(self.T): return out
        g = np.floor(P[:, [0, 2]] / CELL).astype(np.int64); key = self._key(g[:, 0], g[:, 1])
        s, e = np.searchsorted(self.key, key, 'left'), np.searchsorted(self.key, key, 'right'); m = e - s
        for c0 in range(0, len(P), 50_000):
            mm = m[c0:c0 + 50_000]; qi = np.repeat(np.arange(c0, c0 + len(mm)), mm)
            if not len(qi): continue
            ti = self.tri[np.repeat(s[c0:c0 + 50_000], mm) + (np.arange(mm.sum()) - np.repeat(np.cumsum(mm) - mm, mm))]
            A, B, C = self.T[ti, 0], self.T[ti, 1], self.T[ti, 2]; x, z = P[qi, 0], P[qi, 2]
            d = (B[:, 2] - C[:, 2]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 2] - C[:, 2])
            ok = np.abs(d) > 1e-12; d = np.where(ok, d, 1.0)
            l1 = ((B[:, 2] - C[:, 2]) * (x - C[:, 0]) + (C[:, 0] - B[:, 0]) * (z - C[:, 2])) / d
            l2 = ((C[:, 2] - A[:, 2]) * (x - C[:, 0]) + (A[:, 0] - C[:, 0]) * (z - C[:, 2])) / d
            l3 = 1 - l1 - l2; eps = -1e-9
            hy = l1 * A[:, 1] + l2 * B[:, 1] + l3 * C[:, 1]; dy = hy - P[qi, 1]
            hit = ok & (l1 >= eps) & (l2 >= eps) & (l3 >= eps) & (dy <= up) & (dy >= -down)
            if hit.any(): np.fmax.at(out, qi[hit], hy[hit])
        return out


def open_edges(T, owners, own, xc=False):
    """края версии куска без близнеца: ребро только у одного треугольника куска и ни у одного соседа той же версии
    -> (номер треугольника, номер ребра)"""
    n = len(T)
    if not n: return np.zeros(0, int), np.zeros(0, int), np.zeros(0, bool)
    K = edge_keys(T)
    _, inv, cnt = np.unique(K, axis=0, return_inverse=True, return_counts=True)
    idx = np.nonzero(cnt[inv.ravel()] == 1)[0]
    if xc:
        tw = owners.twin(K[idx], own); xc = owners.twin_xcell(K[idx], own)
        isx = np.zeros(n * 3, bool); isx[idx[tw & xc]] = True
        idx = idx[~tw | xc]
        return idx % n, idx // n, isx[idx]
    idx = idx[~owners.twin(K[idx], own)]
    return idx % n, idx // n, np.zeros(len(idx), bool)


def skirt_edges(T, owners, own, gidx, xc=False):
    """открытые края земли, за которыми земля -> (номер треугольника, ребро k, глубина юбки, нормаль наружу XZ;
    глубина <= SKIRT_DEPTH + SKIRT_TOL — щель в плоскости)"""
    T = np.asarray(T, np.float64).reshape(-1, 3, 3)
    ti, k, isx = open_edges(T, owners, own, xc)
    if not len(ti): return ti, k, np.zeros(0), np.zeros((0, 2))
    g = ground_mask(T)[ti]; ti, k, isx = ti[g], k[g], isx[g]
    a, b, c = T[ti, k], T[ti, (k + 1) % 3], T[ti, (k + 2) % 3]
    d = (b - a)[:, [0, 2]]; L = np.linalg.norm(d, axis=1)
    nrm = np.stack([d[:, 1], -d[:, 0]], 1) / np.maximum(L, 1e-9)[:, None]
    side = ((c - a)[:, [0, 2]] * nrm).sum(1); nrm *= np.where(side > 0, -1.0, 1.0)[:, None]   # наружу, от третьей вершины
    dep = np.full(len(ti), np.nan)
    for t in (0.25, 0.5, 0.75):
        p = a + (b - a) * t; q = p.copy(); q[:, [0, 2]] += nrm * PROBE
        dep = np.fmax(dep, p[:, 1] - gidx.top(q) + SKIRT_DEPTH)
    m = (L > 1e-4) & np.isfinite(dep) & (~isx | (L >= XCELL_MINLEN))   # общий с другой клеткой край — только длинный (цена: треугольники юбок)
    return ti[m], k[m], np.clip(dep[m], SKIRT_DEPTH, SKIRT_DROP + SKIRT_DEPTH), nrm[m]


def merge_chains(T, ti, k, dep, nrm):
    """края юбок -> цепочки: края по прямой (вершина общая только у двух краёв, отклонение <= CHAIN_DEV) — одна полоса.
    -> (C, глубина, нормаль): C — список массивов номеров вершин цепочки по порядку в супе версии (3·треугольник + угол);
    глубина — наибольшая, нормаль наружу — первого края. Верх полосы — ВСЕ вершины цепочки, а не только концы: край юбки
    совпадает с краями земли бит в бит, без Т-стыка (длинное ребро поверх коротких на GE даёт щель в пиксель)"""
    T = np.asarray(T, np.float64).reshape(-1, 3, 3)
    ia, ib = 3 * ti + k, 3 * ti + (k + 1) % 3
    if not len(ia): return [], np.zeros(0), np.zeros((0, 2))
    P = T.reshape(-1, 3)
    _, vid = np.unique(np.round(P * Q).astype(np.int64), axis=0, return_inverse=True); vid = vid.ravel()
    ka, kb = vid[ia], vid[ib]
    inc = {}
    for e, (x, y) in enumerate(zip(ka.tolist(), kb.tolist())):
        inc.setdefault(x, []).append(e); inc.setdefault(y, []).append(e)
    used = np.zeros(len(ia), bool); C, D, N = [], [], []
    for e0 in range(len(ia)):
        if used[e0]: continue
        used[e0] = True
        s_key, e_key, dd = ka[e0], kb[e0], dep[e0]; ch = [ia[e0], ib[e0]]
        for fwd in (True, False):   # растим цепочку с конца, потом с начала
            while True:
                key = e_key if fwd else s_key
                lst = inc.get(key, []); nb = [e for e in lst if not used[e]]
                if len(lst) != 2 or len(nb) != 1: break
                e = nb[0]; nk, nref = (kb[e], ib[e]) if ka[e] == key else (ka[e], ia[e])
                p0, p1 = (P[ch[0]], P[nref]) if fwd else (P[nref], P[ch[-1]])
                dv = p1 - p0; Ln = np.linalg.norm(dv)
                if Ln < 1e-6: break
                mid = P[ch[-1]] if fwd else P[ch[0]]   # вершина, которая уйдёт внутрь отрезка
                if np.linalg.norm(np.cross(mid - p0, dv)) / Ln > CHAIN_DEV: break
                used[e] = True; dd = max(dd, dep[e])
                if fwd: e_key = nk; ch.append(nref)
                else: s_key = nk; ch.insert(0, nref)
        C.append(np.array(ch, np.int64)); D.append(dd); N.append(nrm[e0])
    return C, np.array(D), np.array(N).reshape(-1, 2)


def skirt_soup(v, C, D, N):
    """вершины версии куска v (структурный массив, по 3 на треугольник: x y z u v c) и цепочки -> вершины юбок того же
    типа: веер — верх по всем вершинам цепочки (рёбра земли), низ — отрезок концов, сдвинутый на глубину по y (у щели в
    плоскости — наружу-вниз); n вершин цепочки -> n треугольников"""
    if not len(C): return v[:0]
    out = []
    for ch, d, nr in zip(C, D, N):
        flat = d <= SKIRT_DEPTH + SKIRT_TOL + 1e-9
        dy = REACH_DOWN if flat else d; ox, oz = (nr[0] * REACH_OUT, nr[1] * REACH_OUT) if flat else (0.0, 0.0)
        top = v[ch]; lo = top[[0, -1]].copy()
        for w in lo: w['y'] -= dy; w['x'] += ox; w['z'] += oz
        n = len(ch) - 1; t = np.empty(3 * (n + 1), v.dtype)
        t[0:3 * n:3], t[1:3 * n:3] = top[:-1], top[1:]; t[2:3 * n:3] = lo[0]   # веер из нижнего начала
        t[3 * n], t[3 * n + 1], t[3 * n + 2] = top[-1], lo[1], lo[0]
        out.append(t)
    return np.concatenate(out)


def plan(pieces, cells=None, texs=None, xcell_vers=(0, 1)):
    """pieces: [(флаги, ближние (n,3,3), дальние (m,3,3))] — все куски города (номер = место в списке)
    -> ({номер: (ближние отрезки, дальние отрезки)}, сводка); отрезки (A, B, глубина, нормаль). Юбки — непрозрачным без слоёв"""
    solid = lambda fl: not fl & (1 | 2 | 4 | 64)
    gidx = GroundIndex(np.concatenate([p[1] for p in pieces if solid(p[0]) and len(p[1])] or [np.zeros((0, 3, 3))]))
    owners = [EdgeOwners([(i, p[1 + v]) for i, p in enumerate(pieces) if not p[0] & 4], cells, texs) for v in (0, 1)]
    out, cnt = {}, np.zeros((2, 4), int)
    for i, (fl, Tn, Tf) in enumerate(pieces):
        if not solid(fl): continue
        r = []
        for v, T in ((0, Tn), (1, Tf)):
            T = np.asarray(T, np.float64).reshape(-1, 3, 3)
            seg = merge_chains(T, *skirt_edges(T, owners[v], i, gidx, cells is not None and v in xcell_vers)); r.append(seg)
            cnt[v] += [len(T), len(seg[0]), int((seg[1] <= SKIRT_DEPTH + SKIRT_TOL + 1e-9).sum()), sum(len(c) for c in seg[0])]
        out[i] = tuple(r)
    msg = (f'юбки швов (правка 106): ближние — {cnt[0, 1]:,} полос (из них в плоскости {cnt[0, 2]:,}; +{cnt[0, 3]:,} треуг., '
           f'+{100 * cnt[0, 3] / max(cnt[0, 0], 1):.1f}%); дальние — {cnt[1, 1]:,} полос (в плоскости {cnt[1, 2]:,}; '
           f'+{cnt[1, 3]:,}, +{100 * cnt[1, 3] / max(cnt[1, 0], 1):.1f}%)')
    return out, msg
