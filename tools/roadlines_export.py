#!/usr/bin/env python3
"""№824 (слово Роба 18.10, режим «мультик»): «дороги бледные, не хватает контраста — добавить контур вдоль асфальтовой дороги, только там, где дорога для
машин встречается с полом/тротуаром». Офлайн: край асфальта проезжей части уровня -> roadlines.shr (формат TLN2, как toonlines.shr; читает и рисует
viewer/main_levels.h toonLinesLoad/toonLinesDraw).

  roadlines_export.py LEVEL.shr TRAFFIC.shr OUT.shr [--texsrc LEVEL.shr.texsrc.json] [--names texnames.json] [--plot X Z R PNG] [--report FILE.json]

Откуда что берётся (всё по данным уровня, имена — только для глаз и для отсева «не дорога»):
  1. Треугольники города — куски level.shr (owner 0, tools/shr7read.py), без полупрозрачных и неба, только лежачие (|ny| >= 0.5; обход после tools/wind.c
     может быть развёрнут, поэтому знак нормали не смотрим).
  2. Какие текстуры — асфальт проезжей части. Точки полос traffic.shr (TrPt всех полос всех дорог, как их водит трафик) -> треугольник земли под точкой
     (по XZ, ближайший по высоте, не дальше 0.6 м) -> доля точек по текстурам. Основная доля — всегда одно семейство имён диска, rd<N>_* и asphalt_*
     (L1: rd2_norm 40 %, rd1_norm 21 %, rd2_country 20 %, rd2_crosswalk 9 %, asphalt_norm 2.5 %; L2: rd2_norm 71 %, asphalt_norm 11 %, rd2_crosswalk 10 %, rd3_cobble 4 %;
     L3: rd2_norm 66 %, rd3_cobblebrown 17 %). Порог доли точек сам асфальт от «по чему ещё ездят» не отделяет: деревянный причал dockwood 6.5 % в L3 и рельсы traintracks
     2.6 % в L2 (переезд) «ездят» чаще, чем редкие настоящие варианты дороги rd2_crosswalk_country 1.1 %, rd2_parking 0.5 %; а у rd2_striped (разметка въезда на стоянку)
     точек нет совсем, но обвести его линией внутри покрытия — ошибка. Поэтому асфальт = всё семейство ROAD_RE (кроме переходов дорога-трава и пробных, ROAD_NOT_RE), а данные
     полос работают проверкой: в отчёте каждая «ездимая» текстура вне семейства (причал, рельсы, грунтовая подъездная, решётки) выписана с долей точек, чтобы глазами убедиться,
     что дорогой её называть нельзя; без имён (нет texsrc.json) асфальт = доля точек не меньше NONAME_SHARE.
  3. Край. Рёбра треугольников асфальта: ребро без пары у другого асфальта (вершины сварены по позиции в 2 см) — кандидат. Каждый кандидат проверяется ещё и по
     покрытию: вдоль ребра каждые COV_STEP м берём точку в COV_OUT м наружу; если там под ней лежит другой треугольник асфальта (по XZ, высота в COV_DY) — это шов
     (Т-стык, щель сварки), а не край. Подряд идущие непокрытые точки — край; границы отрезков уточняются делением пополам до ~2 см. Линия лежит у самого края асфальта
     (не вынесена наружу) и поднята на LIFT = 10 см — высота бордюра; ниже она тонет в дороге на скользящем угле (глубина линий в движке — tlDepth, как у линий мира).
  4. Склейка и упрощение: отрезки одной цепочки (вершины сварены в 3 см, степень узла 2) соединяются, Дуглас-Пекер 3 см, потом режем по границам клеток 64 м
     (клетка линии = клетка её середины — отрезок не пересекает границу) и не длиннее LEN_MAX (рёбра в guard band GE: у города нарезка 7/14 м).
  5. Запись TLN2: 'TLN2', u32 ncell, u32 nline, клетки (i16 cx, i16 cz, u32 первая, u32 число), линии 6 x i16 (x1 y1 z1 x2 y2 z2, см от угла клетки (cx*64, 0, cz*64)).
Отчёт (stdout, --report JSON): имена текстур асфальта с долей точек, отброшенные «ездимые», число линий, клеток, длина края, линий в круге 60 м вокруг точек полос (среднее/макс)."""
import argparse, collections, json, math, os, re, struct, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read

CELL = 64.0                     # клетка TLN2, м (viewer/main_levels.h TL_CELL)
TL_RANGE = 60.0                 # дальность линий в движке, м (TL_RANGE)
LIFT = 0.10                     # линия над асфальтом, м. Замер в эмуляторе 18.10 (tests: камера вдоль улицы 2.7 м над землёй): при 3 см линия у края тонет в дороге уже дальше ~8 м (глубина 16 бит,
                                # скользящий угол: земля меняет глубину на 1–2 м за пиксель), при 10 см видна непрерывно до дальности линий; ступень бордюра в данных 7–12 см (медиана 7–10, p90 12–19 по L1–L3)
LEN_MIN = 0.30                  # края короче (по XZ) отбрасываем
LEN_MAX = 16.0                  # длиннее режем: guard band GE, ближний город нарезан 7/14 м
WELD = 0.02                     # сварка вершин асфальта, м
COV_STEP, COV_OUT, COV_DY = 0.5, 0.15, 0.40   # шаг проб по ребру, вынос точки наружу, допуск высоты соседнего асфальта, м
CHAIN_WELD, DP_TOL = 0.03, 0.03                # склейка цепочек и упрощение, м
UP_NY = 0.5                     # лежачий треугольник: |ny| >= UP_NY
HIT_DY = 0.6                    # точка полосы -> земля под ней в пределах по высоте, м
CORR_PAD = 1.5                  # коридор полосы (только для отчёта): ширина/2 + CORR_PAD м; доля площади текстуры в коридорах — глазам, асфальт она не решает
ROAD_RE = re.compile(r'^(rd[0-9]+_|asphalt)', re.I)   # семейство имён дорожных текстур диска (rd1_norm, rd2_country, rd3_cobble, asphalt_normbrown ...)
ROAD_NOT_RE = re.compile(r'grasstrans|test', re.I)    # переходы дорога-трава и пробные: не покрытие
NONAME_SHARE = 0.02             # без имён текстур: асфальт = доля точек полос не меньше


class TriGrid:
    """Равномерная сетка по XZ: тр-ки по клеткам их габарита (CSR); покрытие точек и высота плоскости под точкой."""
    def __init__(self, P, cs=8.0):
        self.cs = cs; n = len(P)
        self.P = P
        a, b, c = P[:, 0], P[:, 1], P[:, 2]
        self.ax, self.az, self.ay = a[:, 0], a[:, 2], a[:, 1]
        self.e1x, self.e1z = b[:, 0] - a[:, 0], b[:, 2] - a[:, 2]
        self.e2x, self.e2z = c[:, 0] - a[:, 0], c[:, 2] - a[:, 2]
        det = self.e1x * self.e2z - self.e1z * self.e2x
        self.ok = np.abs(det) > 1e-7
        self.idet = np.where(self.ok, 1.0 / np.where(self.ok, det, 1.0), 0.0)
        self.dyu, self.dyv = b[:, 1] - a[:, 1], c[:, 1] - a[:, 1]
        if n == 0:
            self.empty = True; return
        self.empty = False
        mn = P[:, :, [0, 2]].min(1); mx = P[:, :, [0, 2]].max(1)
        self.x0 = float(mn[:, 0].min()) - 1.0; self.z0 = float(mn[:, 1].min()) - 1.0
        i0 = np.floor((mn[:, 0] - self.x0) / cs).astype(np.int64); i1 = np.floor((mx[:, 0] - self.x0) / cs).astype(np.int64)
        j0 = np.floor((mn[:, 1] - self.z0) / cs).astype(np.int64); j1 = np.floor((mx[:, 1] - self.z0) / cs).astype(np.int64)
        self.nz = int(j1.max()) + 3
        nx = i1 - i0 + 1; nzc = j1 - j0 + 1; cnt = nx * nzc
        tot = int(cnt.sum()); tri = np.repeat(np.arange(n), cnt)
        loc = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nxr = np.repeat(nx, cnt)
        cell = (np.repeat(i0, cnt) + loc % nxr) * self.nz + (np.repeat(j0, cnt) + loc // nxr)
        order = np.argsort(cell, kind='stable')
        cs_ = cell[order]; self.tri = tri[order]
        self.ucell, self.ust = np.unique(cs_, return_index=True)
        self.uen = np.append(self.ust[1:], len(cs_))

    def cell_ids(self, x, z):
        i = np.floor((x - self.x0) / self.cs).astype(np.int64); j = np.floor((z - self.z0) / self.cs).astype(np.int64)
        return i * self.nz + j

    def query(self, x, z, eps=1e-9):
        """-> (список индексов запроса, список тр-ков, высота плоскости) всех пар «точка внутри тр-ка по XZ»"""
        if self.empty or len(x) == 0:
            return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
        cid = self.cell_ids(x, z); uq, inv = np.unique(cid, return_inverse=True)
        pos = np.searchsorted(self.ucell, uq); QI, TI, YY = [], [], []
        order = np.argsort(inv, kind='stable'); inv_s = inv[order]; ub = np.searchsorted(inv_s, np.arange(len(uq) + 1))
        for k, c in enumerate(uq):
            p = pos[k]
            if p >= len(self.ucell) or self.ucell[p] != c: continue
            qi = order[ub[k]:ub[k + 1]]; ti = self.tri[self.ust[p]:self.uen[p]]
            ti = ti[self.ok[ti]]
            if not len(ti): continue
            dx = x[qi][:, None] - self.ax[ti][None, :]; dz = z[qi][:, None] - self.az[ti][None, :]
            u = (dx * self.e2z[ti][None, :] - dz * self.e2x[ti][None, :]) * self.idet[ti][None, :]
            v = (dz * self.e1x[ti][None, :] - dx * self.e1z[ti][None, :]) * self.idet[ti][None, :]
            m = (u >= -eps) & (v >= -eps) & (u + v <= 1 + eps)
            a_, b_ = np.nonzero(m)
            if not len(a_): continue
            QI.append(qi[a_]); TI.append(ti[b_])
            YY.append(self.ay[ti[b_]] + u[a_, b_] * self.dyu[ti[b_]] + v[a_, b_] * self.dyv[ti[b_]])
        if not QI: return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
        return np.concatenate(QI), np.concatenate(TI), np.concatenate(YY)

    def covered(self, x, y, z, dy):
        """для каждой точки: лежит ли под ней (по XZ) треугольник сетки с высотой плоскости в пределах dy от y"""
        out = np.zeros(len(x), bool)
        qi, ti, yy = self.query(x, z)
        if len(qi):
            ok = np.abs(yy - y[qi]) <= dy
            out[qi[ok]] = True
        return out


def tex_names(ts_path, names_path, ntex):
    """номер текстуры -> имя (по level.shr.texsrc.json и словарю sha256-url -> имена диска, tools/notoon_list.py names_by_digest); нет данных — '#N'"""
    res = ['#%d' % i for i in range(ntex)]
    if not ts_path or not Path(ts_path).exists(): return res
    ts = json.loads(Path(ts_path).read_text())['tex']
    names = json.loads(Path(names_path).read_text()) if names_path and Path(names_path).exists() else {}
    for i, t in enumerate(ts[:ntex]):
        if not t: continue
        d = t['url'].split('/')[-1].split('.')[0]
        res[i] = '|'.join(names.get(d, ['#%d' % i]))
    return res


def read_lanes(path):
    """traffic.shr (TRF1) -> (точки полос Nx3, ширина дороги на точку, id дороги); формат viewer/traffic.h (TrHeader/TrRoad/TrPt)"""
    b = Path(path).read_bytes(); assert b[:4] == b'TRF1', 'не TRF1'
    u = struct.unpack_from('<' + 'I' * 63, b, 4)
    nRoad, offRoad, nPt, offPt = u[4], u[5], u[6], u[7]
    pts = np.frombuffer(b, np.float32, nPt * 4, offPt).reshape(-1, 4).astype(np.float64)
    P, W, R = [], [], []
    for i in range(nRoad):
        (startJ, endJ, rev, lanes, fl, maxc, spd, _p8, first, npt, _p16, length, width, _pad) = struct.unpack_from('<HHHHBBBBIHHfff', b, offRoad + 32 * i)
        for k in range(lanes):
            seg = pts[first + k * npt: first + (k + 1) * npt, :3]
            P.append(seg); W.append(np.full(len(seg), width)); R.append(np.full(len(seg), i))
    return np.concatenate(P), np.concatenate(W), np.concatenate(R)


def corridor_share(Pc, area, cen, lanes, widths, rids):
    """доля площади каждого треугольника, центр которого в коридоре полос: |XZ-расстояние до отрезка полосы| <= ширина/2 + CORR_PAD, высота центра близко к полосе"""
    CS = 8.0; x0 = cen[:, 0].min(); z0 = cen[:, 2].min()
    cx = np.floor((cen[:, 0] - x0) / CS).astype(np.int64); cz = np.floor((cen[:, 2] - z0) / CS).astype(np.int64); NZ = int(cz.max()) + 3
    key = cx * NZ + cz; order = np.argsort(key, kind='stable'); ks = key[order]
    inside = np.zeros(len(cen), bool)
    for i in range(len(lanes) - 1):
        if rids[i] != rids[i + 1]: continue
        a, b = lanes[i], lanes[i + 1]; R = widths[i] / 2 + CORR_PAD
        i0, i1 = int((min(a[0], b[0]) - R - x0) // CS), int((max(a[0], b[0]) + R - x0) // CS)
        j0, j1 = int((min(a[2], b[2]) - R - z0) // CS), int((max(a[2], b[2]) + R - z0) // CS)
        cand = []
        for ii in range(i0, i1 + 1):
            for jj in range(j0, j1 + 1):
                k = ii * NZ + jj; lo = np.searchsorted(ks, k, 'left'); hi = np.searchsorted(ks, k, 'right')
                if hi > lo: cand.append(order[lo:hi])
        if not cand: continue
        c = np.concatenate(cand); px = cen[c, 0] - a[0]; pz = cen[c, 2] - a[2]; dx = b[0] - a[0]; dz = b[2] - a[2]
        t = np.clip((px * dx + pz * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
        d = np.hypot(px - t * dx, pz - t * dz)
        inside[c[(d <= R) & (np.abs(cen[c, 1] - (a[1] + t * (b[1] - a[1]))) < 1.5)]] = True
    return inside


def classify(P, TEX, nrm_y, lanes, widths, rids, names):
    """-> (множество номеров текстур асфальта, таблица отчёта). см. п. 2 докстринга"""
    ntex = len(names)
    # точки полос -> текстура земли под точкой (ближайшая по высоте в пределах HIT_DY)
    up = (np.abs(nrm_y) >= UP_NY) & (TEX >= 0)   # TEX -1 — кусок без текстуры
    g = TriGrid(P[up]); tex_up = TEX[up]
    qi, ti, yy = g.query(lanes[:, 0], lanes[:, 2])
    hits = collections.Counter(); npt = len(lanes); nground = 0
    if len(qi):
        dy = np.abs(yy - lanes[qi, 1]); o = np.lexsort((dy, qi)); qi, ti, dy = qi[o], ti[o], dy[o]
        first = np.r_[True, qi[1:] != qi[:-1]]
        for q, t, d in zip(qi[first], ti[first], dy[first]):
            if d <= HIT_DY: hits[int(tex_up[t])] += 1; nground += 1
    # площадь текстуры и её часть в коридорах полос
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]
    area = np.abs(e1[:, 0] * e2[:, 2] - e1[:, 2] * e2[:, 0]) * 0.5
    inside = corridor_share(P, area, P.mean(1), lanes, widths, rids)
    tot = np.bincount(TEX[up], weights=area[up], minlength=ntex); ins = np.bincount(TEX[up & inside], weights=area[up & inside], minlength=ntex)
    asphalt, rows = set(), []
    nonames = not any(ROAD_RE.search(nm) for nm in names)   # texsrc.json нет: имён нет — тогда только доля точек полос (>= NONAME_SHARE), глазами по номерам
    for t in range(ntex):
        nm = names[t]; fam = bool(ROAD_RE.search(nm)) and not ROAD_NOT_RE.search(nm)
        h = hits.get(t, 0); share = ins[t] / tot[t] if tot[t] > 0 else 0.0
        if nonames: fam = h >= NONAME_SHARE * max(nground, 1)
        if fam: asphalt.add(t)
        if h > 0 or fam: rows.append(dict(tex=t, name=nm, lane_points=h, lane_share=h / max(nground, 1), area_m2=float(tot[t]), corridor_share=float(share), asphalt=t in asphalt))
    rows.sort(key=lambda r: (-r['asphalt'], -r['lane_points'], -r['area_m2']))
    return asphalt, rows, nground, npt


def boundary_segments(Pa, grid_a):
    """асфальт (N,3,3) -> отрезки края (M,2,3): ребро без пары + непокрытые вдоль него пробы, с уточнением границы деления пополам"""
    n = len(Pa)
    key = np.round(Pa / WELD).astype(np.int64).reshape(-1, 3)   # (3N, 3) ключ вершины
    _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.reshape(n, 3)
    ea = np.stack([vid[:, 0], vid[:, 1], vid[:, 2]], 1); eb = np.stack([vid[:, 1], vid[:, 2], vid[:, 0]], 1)
    lo = np.minimum(ea, eb).reshape(-1).astype(np.int64); hi = np.maximum(ea, eb).reshape(-1).astype(np.int64)
    ek = lo * (vid.max() + 1) + hi
    uk, inv, cnt = np.unique(ek, return_inverse=True, return_counts=True)
    single = (cnt[inv] == 1)
    tri_i = np.repeat(np.arange(n), 3); slot = np.tile(np.arange(3), n)
    sel = np.nonzero(single)[0]
    A = Pa[tri_i[sel], slot[sel]]; B = Pa[tri_i[sel], (slot[sel] + 1) % 3]; C = Pa[tri_i[sel], (slot[sel] + 2) % 3]
    hl = np.hypot(B[:, 0] - A[:, 0], B[:, 2] - A[:, 2])
    keep = hl >= LEN_MIN; A, B, C, hl = A[keep], B[keep], C[keep], hl[keep]
    nraw = len(A)
    # нормаль наружу (XZ): прочь от третьей вершины
    dx, dz = B[:, 0] - A[:, 0], B[:, 2] - A[:, 2]
    nx, nz = dz / hl, -dx / hl
    side = (C[:, 0] - A[:, 0]) * nx + (C[:, 2] - A[:, 2]) * nz
    nx, nz = np.where(side > 0, -nx, nx), np.where(side > 0, -nz, nz)
    m = np.maximum(2, np.ceil(hl / COV_STEP).astype(np.int64))
    ei = np.repeat(np.arange(len(A)), m); k = np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m)
    tk = (k + 0.5) / m[ei]
    sx = A[ei, 0] + tk * (B[ei, 0] - A[ei, 0]); sy = A[ei, 1] + tk * (B[ei, 1] - A[ei, 1]); sz = A[ei, 2] + tk * (B[ei, 2] - A[ei, 2])
    cov = grid_a.covered(sx + nx[ei] * COV_OUT, sy, sz + nz[ei] * COV_OUT, COV_DY)
    # (покрытие самим собой невозможно: точка снаружи ребра; но тр-к-двойник того же места закрыл бы всё — это и есть наложение слоёв)
    free = ~cov
    segs = []
    # по ребру: подряд идущие непокрытые пробы -> отрезок [t0, t1]; концы, где соседние пробы разного состояния, уточняем делением пополам
    starts = np.r_[0, np.cumsum(m)[:-1]]
    trans = []   # (ребро, t слева, t справа, состояние слева): точка перехода между пробой j и j+1
    runs = []    # (ребро, первая проба, последняя проба) непокрытых серий
    fr = free.reshape(-1)
    for e in range(len(A)):
        s = fr[starts[e]: starts[e] + m[e]]
        if s.all(): runs.append((e, 0, m[e] - 1)); continue
        if not s.any(): continue
        d = np.diff(np.r_[False, s, False].astype(np.int8))
        for a_, b_ in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1): runs.append((e, int(a_), int(b_)))
    # границы: левый конец серии — между пробой a-1 и a, правый — между b и b+1 (если серия не от края ребра)
    def probe(ee, tt):
        sx_ = A[ee, 0] + tt * (B[ee, 0] - A[ee, 0]); sy_ = A[ee, 1] + tt * (B[ee, 1] - A[ee, 1]); sz_ = A[ee, 2] + tt * (B[ee, 2] - A[ee, 2])
        return ~grid_a.covered(sx_ + nx[ee] * COV_OUT, sy_, sz_ + nz[ee] * COV_OUT, COV_DY)   # True — край
    R = np.array(runs, np.int64).reshape(-1, 3) if runs else np.zeros((0, 3), np.int64)
    if len(R):
        e = R[:, 0]; a_, b_ = R[:, 1], R[:, 2]; mm = m[e]
        # левая граница: [ (a-1+.5)/m (покрыто) .. (a+.5)/m (край) ]; если a == 0 — граница в t = 0
        lo_t = np.where(a_ > 0, (a_ - 0.5) / mm, 0.0); hi_t = np.where(a_ > 0, (a_ + 0.5) / mm, 0.0)
        for _ in range(5):
            mid = (lo_t + hi_t) / 2; ed = probe(e, mid)   # край -> граница левее
            hi_t = np.where(a_ > 0, np.where(ed, mid, hi_t), hi_t); lo_t = np.where(a_ > 0, np.where(ed, lo_t, mid), lo_t)
        t0 = np.where(a_ > 0, hi_t, 0.0)
        lo_t = np.where(b_ < mm - 1, (b_ + 0.5) / mm, 1.0); hi_t = np.where(b_ < mm - 1, (b_ + 1.5) / mm, 1.0)
        for _ in range(5):
            mid = (lo_t + hi_t) / 2; ed = probe(e, mid)   # край -> граница правее
            lo_t = np.where(b_ < mm - 1, np.where(ed, mid, lo_t), lo_t); hi_t = np.where(b_ < mm - 1, np.where(ed, hi_t, mid), hi_t)
        t1 = np.where(b_ < mm - 1, lo_t, 1.0)
        P0 = A[e] + t0[:, None] * (B[e] - A[e]); P1 = A[e] + t1[:, None] * (B[e] - A[e])
        S = np.stack([P0, P1], 1)
        S = S[np.hypot(S[:, 1, 0] - S[:, 0, 0], S[:, 1, 2] - S[:, 0, 2]) >= 0.02]
    else:
        S = np.zeros((0, 2, 3))
    return S, nraw


def chains(S):
    """отрезки (M,2,3) -> ломаные: узлы сварены в CHAIN_WELD, склейка по узлам степени 2; Дуглас-Пекер DP_TOL"""
    if not len(S): return []
    q = lambda p: (int(round(p[0] / CHAIN_WELD)), int(round(p[1] / 0.1)), int(round(p[2] / CHAIN_WELD)))
    seen = set(); segs = []
    for a, b in S:
        ka, kb = q(a), q(b)
        if ka == kb: continue
        kk = (ka, kb) if ka < kb else (kb, ka)
        if kk in seen: continue
        seen.add(kk); segs.append((ka, kb, a, b))
    adj = collections.defaultdict(list)
    for i, (ka, kb, a, b) in enumerate(segs): adj[ka].append(i); adj[kb].append(i)
    used = [False] * len(segs); out = []
    def other(i, k): return segs[i][1] if segs[i][0] == k else segs[i][0]
    def pos(i, k): return segs[i][2] if segs[i][0] == k else segs[i][3]
    def walk(i, k):   # от узла k по сегменту i вперёд, пока узлы степени 2
        pts = []
        while True:
            used[i] = True; k2 = other(i, k); pts.append(pos(i, k2))
            nxt = [j for j in adj[k2] if j != i and not used[j]]
            if len(adj[k2]) != 2 or not nxt: break
            i, k = nxt[0], k2
        return pts
    deg_ends = [k for k, v in adj.items() if len(v) != 2]
    for k in deg_ends:
        for i in adj[k]:
            if used[i]: continue
            out.append([pos(i, k)] + walk(i, k))
    for i in range(len(segs)):   # замкнутые петли
        if used[i]: continue
        k = segs[i][0]; out.append([pos(i, k)] + walk(i, k))
    res = []
    for pl in out:
        res.append(dp(np.array(pl), DP_TOL))
    return res


def dp(pl, tol):
    """Дуглас-Пекер по ломаной (N,3), 3D-расстояние до хорды; возвращает вершины, оставшиеся после упрощения"""
    n = len(pl)
    if n <= 2: return pl
    keep = np.zeros(n, bool); keep[0] = keep[-1] = True; stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1: continue
        a, b = pl[i], pl[j]; d = b - a; L2 = float(d @ d)
        P_ = pl[i + 1: j] - a
        if L2 < 1e-12: dist = np.linalg.norm(P_, axis=1)
        else:
            t = np.clip(P_ @ d / L2, 0, 1); dist = np.linalg.norm(P_ - t[:, None] * d, axis=1)
        k = int(np.argmax(dist))
        if dist[k] > tol: keep[i + 1 + k] = True; stack.append((i, i + 1 + k)); stack.append((i + 1 + k, j))
    return pl[keep]


def split_lines(polys):
    """ломаные -> отрезки (K,2,3), режем по границам клеток CELL и не длиннее LEN_MAX; y поднимаем на LIFT"""
    out = []
    for pl in polys:
        for a, b in zip(pl[:-1], pl[1:]):
            ts = [0.0, 1.0]
            for ax in (0, 2):
                lo, hi = (a[ax], b[ax]) if a[ax] <= b[ax] else (b[ax], a[ax])
                if hi - lo < 1e-9: continue
                for g in range(int(math.floor(lo / CELL)) + 1, int(math.floor(hi / CELL)) + 1):
                    t = (g * CELL - a[ax]) / (b[ax] - a[ax])
                    if 1e-6 < t < 1 - 1e-6: ts.append(t)
            ts = sorted(set(ts))
            for t0, t1 in zip(ts[:-1], ts[1:]):
                p0 = a + t0 * (b - a); p1 = a + t1 * (b - a)
                L = float(np.hypot(p1[0] - p0[0], p1[2] - p0[2])); k = max(1, int(math.ceil(L / LEN_MAX)))
                for s in range(k):
                    q0 = p0 + (p1 - p0) * (s / k); q1 = p0 + (p1 - p0) * ((s + 1) / k)
                    out.append((q0, q1))
    if not out: return np.zeros((0, 2, 3))
    S = np.array(out); S[:, :, 1] += LIFT
    return S


def write_tln2(path, S):
    """S (K,2,3) метры -> TLN2 (формат tools/psp_export.py write_toon_lines)"""
    L = S.reshape(-1, 6)
    if len(L):
        mid = (L[:, :3] + L[:, 3:]) / 2
        cx = np.floor(mid[:, 0] / CELL).astype(int); cz = np.floor(mid[:, 2] / CELL).astype(int)
        order = np.lexsort((cz, cx)); L, cx, cz = L[order], cx[order], cz[order]
    cells = []; i = 0
    while i < len(L):
        j = i
        while j < len(L) and cx[j] == cx[i] and cz[j] == cz[i]: j += 1
        cells.append((int(cx[i]), int(cz[i]), i, j - i)); i = j
    q = np.zeros((len(L), 6), np.int16)
    for (a, b, f, c_) in cells:
        o = np.array([a * CELL, 0.0, b * CELL, a * CELL, 0.0, b * CELL])
        r = np.round((L[f:f + c_] - o) * 100)
        assert np.abs(r).max() <= 32767, 'линия дальше 327 м от угла клетки'
        q[f:f + c_] = r.astype(np.int16)
    out = b'TLN2' + struct.pack('<II', len(cells), len(L))
    for a, b, f, c_ in cells: out += struct.pack('<hhII', a, b, f, c_)
    Path(path).write_bytes(out + q.tobytes())
    return len(cells), len(L), len(out) + q.nbytes


def read_tln2(path):
    """TLN2 -> (K,2,3) метры (как читает движок; для проверки и рисунка)"""
    b = Path(path).read_bytes(); assert b[:4] == b'TLN2'
    nc, nl = struct.unpack_from('<II', b, 4); p = 12
    cells = [struct.unpack_from('<hhII', b, p + 12 * i) for i in range(nc)]; p += 12 * nc
    q = np.frombuffer(b, np.int16, nl * 6, p).reshape(-1, 6).astype(np.float64) / 100.0
    S = np.zeros((nl, 2, 3))
    for (cx, cz, f, c_) in cells:
        o = np.array([cx * CELL, 0.0, cz * CELL])
        S[f:f + c_, 0] = q[f:f + c_, 0:3] + o; S[f:f + c_, 1] = q[f:f + c_, 3:6] + o
    return S, cells


def draw_cost(S, cells, lanes):
    """сколько линий движок рисует из точек полос: клетки в TL_RANGE м от глаза (прямоугольник клетки), как toonLinesDraw"""
    cc = np.array([(c[0], c[1], c[3]) for c in cells], np.float64).reshape(-1, 3)
    if not len(cc): return 0.0, 0
    n = []
    for p in lanes[::3]:
        ox, oz = cc[:, 0] * CELL, cc[:, 1] * CELL
        ok = (p[0] >= ox - TL_RANGE) & (p[0] <= ox + CELL + TL_RANGE) & (p[2] >= oz - TL_RANGE) & (p[2] <= oz + CELL + TL_RANGE)
        n.append(cc[ok, 2].sum())
    n = np.array(n); return float(n.mean()), int(n.max())


def plot(png, P, TEX, asphalt, S, cx, cz, R, ppm=None):
    from PIL import Image, ImageDraw
    ppm = ppm or max(2, int(960 / (2 * R)))
    W = int(2 * R * ppm); im = Image.new('RGB', (W, W), (40, 40, 40)); dr = ImageDraw.Draw(im)
    def px(x, z): return ((x - (cx - R)) * ppm, (z - (cz - R)) * ppm)
    mn = P[:, :, [0, 2]].min(1); mx = P[:, :, [0, 2]].max(1)
    sel = np.nonzero((mx[:, 0] >= cx - R) & (mn[:, 0] <= cx + R) & (mx[:, 1] >= cz - R) & (mn[:, 1] <= cz + R))[0]
    order = sel[np.argsort(P[sel][:, :, 1].mean(1))]   # низ -> верх
    for i in order:
        t = P[i]; col = (120, 124, 130) if TEX[i] in asphalt else (60 + (TEX[i] * 53) % 120, 90 + (TEX[i] * 97) % 110, 50 + (TEX[i] * 29) % 100)
        dr.polygon([px(t[0, 0], t[0, 2]), px(t[1, 0], t[1, 2]), px(t[2, 0], t[2, 2])], fill=col)
    for a, b in S:
        if min(a[0], b[0]) > cx + R or max(a[0], b[0]) < cx - R or min(a[2], b[2]) > cz + R or max(a[2], b[2]) < cz - R: continue
        dr.line([px(a[0], a[2]), px(b[0], b[2])], fill=(255, 40, 40), width=2)
    im.save(png)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('level'); ap.add_argument('traffic'); ap.add_argument('out')
    ap.add_argument('--texsrc', default=''); ap.add_argument('--names', default=''); ap.add_argument('--report', default='')
    ap.add_argument('--plot', nargs=4, metavar=('X', 'Z', 'R', 'PNG'))
    ap.add_argument('--tex', default='', help='вручную: номера текстур асфальта через запятую (вместо отбора по данным)')
    a = ap.parse_args()
    d = shr7read.load(a.level, far=False, owner=0)
    P, TEX, FL = d['P'], d['TEX'], d['FL']
    hdr = Path(a.level).read_bytes()[:12]; ntex = struct.unpack_from('<I', hdr, 4)[0]
    names = tex_names(a.texsrc or (a.level + '.texsrc.json'), a.names, ntex)
    keep = (FL & (2 | 4)) == 0
    P, TEX, FL = P[keep], TEX[keep], FL[keep]
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]; nrm = np.cross(e1, e2); ln = np.linalg.norm(nrm, axis=1); ln[ln == 0] = 1
    ny = nrm[:, 1] / ln
    lanes, widths, rids = read_lanes(a.traffic)
    if a.tex: asphalt = set(int(x) for x in a.tex.split(',')); rows = []; nground = npt = 0
    else: asphalt, rows, nground, npt = classify(P, TEX, ny, lanes, widths, rids, names)
    print('ASPHALT textures (%d), точки полос на земле %d из %d:' % (len(asphalt), nground, npt if rows else 0))
    for r in rows:
        print('  %s %4d %-34s точек %4d (%5.1f %%)  площадь %8.0f м2  в коридоре %3.0f %%' % ('+' if r['asphalt'] else '-', r['tex'], r['name'][:34], r['lane_points'], 100 * r['lane_share'], r['area_m2'], 100 * r['corridor_share']))
    dropped = [r for r in rows if not r['asphalt'] and r['lane_points'] > 0]
    print('  отброшено «ездимых» (не семейство дорожных): ' + ', '.join('%s %.1f %%' % (r['name'], 100 * r['lane_share']) for r in dropped if r['lane_share'] >= 0.005))
    up = (np.abs(ny) >= UP_NY) & np.isin(TEX, list(asphalt))
    Pa = P[up]; print('треугольников асфальта: %d (из %d)' % (len(Pa), len(P)))
    steep = (np.abs(ny) < UP_NY) & np.isin(TEX, list(asphalt)); print('  стоячих тр-ков асфальта отброшено: %d' % steep.sum())
    grid_a = TriGrid(Pa)
    S, nraw = boundary_segments(Pa, grid_a)
    print('рёбер-кандидатов (без пары, >= %.2f м): %d; отрезков после проверки покрытия: %d' % (LEN_MIN, nraw, len(S)))
    polys = chains(S)
    lines = split_lines(polys)
    ncell, nline, nbytes = write_tln2(a.out, lines)
    S2, cells = read_tln2(a.out)
    length = float(np.hypot(S2[:, 1, 0] - S2[:, 0, 0], S2[:, 1, 2] - S2[:, 0, 2]).sum())
    mean_d, max_d = draw_cost(S2, cells, lanes)
    print('ИТОГ: линий %d в клетках %d, ломаных %d, длина края %.0f м, файл %d Б; в круге %g м от полос рисуется в среднем %.0f, максимум %d линий' % (nline, ncell, len(polys), length, nbytes, TL_RANGE, mean_d, max_d))
    if a.report:
        Path(a.report).write_text(json.dumps(dict(level=str(a.level), asphalt=[names[t] for t in sorted(asphalt)], table=rows, lines=nline, cells=ncell, polylines=len(polys),
                                                  edge_length_m=length, bytes=nbytes, draw_mean=mean_d, draw_max=max_d), ensure_ascii=False, indent=1))
    if a.plot:
        plot(a.plot[3], P, TEX, asphalt, S2, float(a.plot[0]), float(a.plot[1]), float(a.plot[2]))


if __name__ == '__main__':
    main()
