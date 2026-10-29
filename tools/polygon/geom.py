#!/usr/bin/env python3
"""Геометрия уровня для регистратора полигона (tools/polygon/registry.py): что ВИДНО (куски города level.shr, tools/shr7read.py) против
того, во что УПИРАЕТСЯ (коллизия COL1, tools/col_check.py parse_col). Только чтение данных уровня, без игры.

  Geo.from_level(level.shr)  — образцы видимого (точки на треугольниках через ≤ 1 м) и опор коллизии (земля n.y ≥ 0.5, верх ящиков)
  Geo(R, RF, CT, CB)         — то же из массивов (тесты: синтетический мини-мир числами)
  geo.holes()                — дыры по данным: «видимая земля без коллизии» (hole_visible) и «коллизия без видимой земли» (hole_phantom):
                               клетка 2 м, высоты сравниваются ± 1 м; место — связная группа ≥ HOLE_MIN клеток (мелочь — шов, не дыра)
  geo.invisible(x, y, z)     — у точки удара о стену нет видимой геометрии (± 1.2 м по плоскости, от −0.5 до +2.5 м по высоте)
  geo.crossings(seg)         — отрезки следа проб, прошедшие сквозь видимую непрозрачную стену глубже 0.6 м (сквозь видимую стену)

Флаги кусков (tools/psp_export.py): 1 — альфа-тест (листва, решётки), 2 — полупрозрачный, 4 — служебный (anatomy.py не рисует).
Стена для «сквозь» — только непрозрачная (флаги 1, 2, 4 сняты): сквозь куст проезжать можно (принцип доводки, п. 4)."""
import math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CELL = 2.0        # м: клетка сравнения «видно / держит»
DY = 1.0          # м: высоты совпали
HOLE_MIN = 4      # клеток 2 м (16 м²): меньше — шов или край, не дыра
WALL_NY = 0.3     # |n.y| меньше — стена
PAST = 0.6        # м: насколько глубже плоскости стены должен оказаться бот, чтобы считать «прошёл сквозь»
BODY = (0.8, 0.9)  # м над точкой бота: машина (низ колёс -> середина кузова), Гомер (ступни -> пояс)


def _normals(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); L = np.linalg.norm(n, axis=1, keepdims=True); L[L == 0] = 1
    return n / L


def sample_tris(T, step=1.0):
    """точки на треугольниках (N,3,3): решётка барицентрических точек, шаг ≤ step м -> (M,3) точки и (M,) номер треугольника"""
    if not len(T): return np.zeros((0, 3)), np.zeros(0, np.int64)
    e = np.max([np.linalg.norm(T[:, a] - T[:, b], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], 0)
    n = np.maximum(1, np.ceil(e / step)).astype(int)
    P, I = [], []
    for k in np.unique(n):
        idx = np.nonzero(n == k)[0]
        uv = np.array([(i / k, j / k) for i in range(k + 1) for j in range(k + 1 - i)])   # (S,2)
        t = T[idx]
        pts = t[:, None, 0] + uv[None, :, 0, None] * (t[:, None, 1] - t[:, None, 0]) + uv[None, :, 1, None] * (t[:, None, 2] - t[:, None, 0])
        P.append(pts.reshape(-1, 3)); I.append(np.repeat(idx, len(uv)))
    return np.concatenate(P), np.concatenate(I)


def box_tops(B):
    """ящики COL1 (N,16: c, ax, ay, az, h) -> треугольники верхней грани (ось ящика, ближайшая к вертикали)"""
    out = []
    for b in B:
        c, axes, h = b[0:3], [b[3:6], b[6:9], b[9:12]], b[12:15]
        k = int(np.argmax([abs(a[1]) for a in axes]))
        if abs(axes[k][1]) < .7: continue
        up = axes[k] * (1 if axes[k][1] > 0 else -1) * h[k]
        o = [i for i in range(3) if i != k]; u, v = axes[o[0]] * h[o[0]], axes[o[1]] * h[o[1]]
        q = [c + up - u - v, c + up + u - v, c + up + u + v, c + up - u + v]
        out += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
    return np.asarray(out, np.float64).reshape(-1, 3, 3)


def _key(cx, cz, cy=None):
    k = (cx.astype(np.int64) + 100000) * 200003 + (cz.astype(np.int64) + 100000)
    return k if cy is None else k * 4099 + (cy.astype(np.int64) + 2048)


class Geo:
    def __init__(self, R, RF, CT, CB=None):
        """R — видимые треугольники (N,3,3) движка, RF — их флаги; CT — треугольники коллизии (M,3,3); CB — ящики (K,16)"""
        self.R = np.asarray(R, np.float64).reshape(-1, 3, 3); self.RF = np.asarray(RF, np.int64).reshape(-1)
        CT = np.asarray(CT, np.float64).reshape(-1, 3, 3)
        self.CT = CT; self.CB = np.zeros((0, 16)) if CB is None else np.asarray(CB, np.float64).reshape(-1, 16)
        self.RN = _normals(self.R) if len(self.R) else np.zeros((0, 3))
        cn = _normals(CT) if len(CT) else np.zeros((0, 3))
        ground = CT[np.abs(cn[:, 1]) >= .5] if len(CT) else CT
        tops = box_tops(self.CB)
        self.CG = np.concatenate([ground, tops]) if len(tops) else ground
        # видимое: все куски кроме служебных (4); видимая земля: |n.y| > 0.55, не полупрозрачная (вода, стёкла) и не служебная
        vis = (self.RF & 4) == 0
        self.Rs, self.Ri = sample_tris(self.R[vis], 1.0); self.Ri = np.nonzero(vis)[0][self.Ri] if len(self.Ri) else self.Ri
        self.vis_key = set(_key(np.floor(self.Rs[:, 0]), np.floor(self.Rs[:, 2]), np.floor(self.Rs[:, 1])).tolist())
        self._walls = None

    @classmethod
    def from_level(cls, path):
        sys.path.insert(0, str(ROOT / 'tools'))
        import shr7read, col_check
        L = shr7read.load(path); b, H = col_check.load(path); C = col_check.parse_col(b, H['col'])
        return cls(L['P'], L['FL'], C['tri'][:, :3, :], C['box'])

    # ------------------------------------------------------------------ дыры по данным
    def holes(self):
        """-> [dict(kind, x, y, z, cells)] — места «видимая земля без коллизии» и «коллизия без видимой земли»"""
        out = []
        gm = (np.abs(self.RN[:, 1]) > .55) & ((self.RF & 6) == 0) if len(self.R) else np.zeros(0, bool)
        Vg, _ = sample_tris(self.R[gm], CELL * .7)
        Cg, _ = sample_tris(self.CG, CELL * .7)
        def keys(P, dil):
            cx, cz, cy = np.floor(P[:, 0] / CELL), np.floor(P[:, 2] / CELL), np.floor(P[:, 1] / DY)
            if not dil: return _key(cx, cz, cy)
            return np.concatenate([_key(cx, cz, cy + d) for d in (-1, 0, 1)])
        for kind, A, Bp in (('hole_visible', Vg, Cg), ('hole_phantom', Cg, None)):
            if not len(A): continue
            if Bp is None:   # опора коллизии без видимого: видимое — любые куски (стены, крыши, земля), допуск ± 1 м
                Bv = self.Rs
            else: Bv = Bp
            have = np.unique(keys(Bv, True)) if len(Bv) else np.zeros(0, np.int64)
            M = A[~np.isin(keys(A, False), have)]
            cells = {}
            for p in M:
                c = (int(math.floor(p[0] / CELL)), int(math.floor(p[2] / CELL)))
                cells.setdefault(c, []).append(p[1])
            seen = set()
            for c0 in sorted(cells):
                if c0 in seen: continue
                comp, stack = [], [c0]; seen.add(c0)
                while stack:
                    c = stack.pop(); comp.append(c); y = np.mean(cells[c])
                    for dx in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            w = (c[0] + dx, c[1] + dz)
                            if w in cells and w not in seen and abs(np.mean(cells[w]) - y) < 1.5: seen.add(w); stack.append(w)
                if len(comp) < HOLE_MIN: continue
                xs = [(c[0] + .5) * CELL for c in comp]; zs = [(c[1] + .5) * CELL for c in comp]; ys = [np.mean(cells[c]) for c in comp]
                out.append(dict(kind=kind, x=float(np.mean(xs)), y=float(np.mean(ys)), z=float(np.mean(zs)), cells=len(comp)))
        return out

    # ------------------------------------------------------------------ невидимая стена
    def invisible(self, x, y, z, r=1.2, dy0=-.5, dy1=2.5):
        """1 — у точки удара нет видимой геометрии (образцы видимого через 1 м: клетки 1 м вокруг)"""
        for cx in range(math.floor(x - r), math.floor(x + r) + 1):
            for cz in range(math.floor(z - r), math.floor(z + r) + 1):
                for cy in range(math.floor(y + dy0), math.floor(y + dy1) + 1):
                    if int(_key(np.array([cx]), np.array([cz]), np.array([cy]))[0]) in self.vis_key: return False
        return True

    # ------------------------------------------------------------------ сквозь видимую стену
    def _wall_index(self):
        if self._walls is None:
            m = (np.abs(self.RN[:, 1]) < WALL_NY) & ((self.RF & 7) == 0) if len(self.R) else np.zeros(0, bool)
            W = self.R[m]; hi = W[:, :, 1].max(1) - W[:, :, 1].min(1); W = W[hi > .8]   # бордюр и ступенька — не стена
            grid = {}
            for i, t in enumerate(W):
                for gx in range(math.floor(t[:, 0].min() / 4), math.floor(t[:, 0].max() / 4) + 1):
                    for gz in range(math.floor(t[:, 2].min() / 4), math.floor(t[:, 2].max() / 4) + 1):
                        grid.setdefault((gx, gz), []).append(i)
            self._walls = (W, _normals(W) if len(W) else np.zeros((0, 3)), grid)
        return self._walls

    def crossings(self, segs):
        """segs — [(x0, y0, z0, x1, y1, z1, пешком)] (точки бота: машина — низ колёс, Гомер — ступни) -> [(x, y, z, номер отрезка)] —
        прошёл сквозь непрозрачную видимую стену и оказался за ней глубже PAST"""
        W, N, grid = self._wall_index(); out = []
        for si, (x0, y0, z0, x1, y1, z1, foot) in enumerate(segs):
            lift = BODY[1 if foot else 0]; a = np.array([x0, y0 + lift, z0]); b = np.array([x1, y1 + lift, z1]); d = b - a
            if d @ d < 1e-6: continue
            cand = set()
            for gx in range(math.floor(min(x0, x1) / 4), math.floor(max(x0, x1) / 4) + 1):
                for gz in range(math.floor(min(z0, z1) / 4), math.floor(max(z0, z1) / 4) + 1):
                    cand.update(grid.get((gx, gz), ()))
            for i in sorted(cand):
                t = W[i]; e1, e2 = t[1] - t[0], t[2] - t[0]; p = np.cross(d, e2); det = e1 @ p
                if abs(det) < 1e-9: continue
                s = a - t[0]; u = (s @ p) / det
                if u < 0 or u > 1: continue
                q = np.cross(s, e1); v = (d @ q) / det
                if v < 0 or u + v > 1: continue
                tt = (e2 @ q) / det
                if tt < 0 or tt > 1: continue
                n = N[i]; depth = abs((b - t[0]) @ n)   # насколько конец отрезка за плоскостью
                if depth < PAST: continue
                h = a + d * tt; out.append((float(h[0]), float(h[1] - lift), float(h[2]), si)); break
        return out


def read_trace(path):
    """trace.bin инспектора (int32 точка, int32 проба, float x y z) -> отрезки [(x0, y0, z0, x1, y1, z1, пешком)]; проба ≥ 8 — пешком"""
    try: raw = np.fromfile(path, dtype=np.dtype([('pt', '<i4'), ('pr', '<i4'), ('p', '<f4', 3)]))
    except (OSError, ValueError): return []
    segs = []
    for k in range(1, len(raw)):
        a, b = raw[k - 1], raw[k]
        if a['pt'] != b['pt'] or a['pr'] != b['pr']: continue
        segs.append((*map(float, a['p']), *map(float, b['p']), int(b['pr'] >= 8)))
    return segs
