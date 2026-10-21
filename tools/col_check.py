"""Проверка секции коллизии COL1 в файле уровня SHR7 (формат — см. tools/psp_export.py, «Коллизия: секция COL1»).
python tools/col_check.py LEVEL.shr                 -> счётчики, память, проверки, картинки LEVEL_col*.png рядом
python tools/col_check.py LEVEL.shr --png out.png   -> карта сюда (+ out_spawn.png, out_<место>.png — крупные планы)
python tools/col_check.py LEVEL.shr --no-png        -> только проверки
Выход с кодом 1, если есть ошибки формата/ссылок.

Что проверяем:
  * заголовок и границы секции; COL1 лежит до PVS (tools/pvs дописывает PVS в конец)
  * каждый примитив записан во все клетки, которые задевает его xz-габарит (точный габарит; у заборов — все клетки
    ближе 0.5 м к отрезку); лишние ссылки — только предупреждение (габарит в экспорте с запасом)
  * нормали единичные, у земли n = unit(cross(b-a, c-a)) и n.y >= 0; оси ящиков ортонормальны (правая тройка)
  * заборы: заливка от спавна по проходимой земле, заборы — стены. Нормаль должна смотреть в залитую сторону
  * совпадение с отрисовкой: вершины кусков города внутри ящиков/капсул, у земли — ближайшая вершина; то же для
    отзеркаленного по z варианта (если зеркало перепутано, цифры поменяются местами)
Картинка (1 px = 0.5 м, x вправо, z вниз): земля — серый по высоте, крутая земля — красный, стены отрисовки —
светло-серый, ящики — синие контуры, цилиндры/капсулы/сферы — зелёные круги, заборы — жёлтые с засечкой-нормалью,
спавн — пурпурный с курсом, залитая от спавна область — лёгкий синий тон."""
import sys, struct, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

WALK_NY = 0.55   # как в карте высот psp_export.py: |n.y| > 0.55 — можно стоять/ехать
QV = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('pad', '<i2')])
TYPES = ('tri', 'box', 'cyl', 'seg')

def load(path):
    b = Path(path).read_bytes()
    if b[:4] != b'SHR7': sys.exit(f'{path}: не SHR7')
    L = dict(size=len(b))
    L['ntex'], L['npieces'] = struct.unpack_from('<II', b, 4)
    f = struct.unpack_from('<11f', b, 12); L['bb'] = f[:6]; L['spawn'] = f[6:9]; L['heading'] = f[9]; L['lift'] = f[10]
    L['table'], L['ncell'], L['cells'], L['pvs'], L['col'] = struct.unpack_from('<5I', b, 76)
    return b, L

def parse_col(b, off):
    if off == 0: sys.exit('в заголовке @92 ноль: секции COL1 нет')
    if b[off:off + 4] != b'COL1': sys.exit(f'@92 = {off}: там не COL1')
    ox, oz, cell = struct.unpack_from('<3f', b, off + 4)
    W, H, ntri, nbox, ncyl, nseg, nref, flags = struct.unpack_from('<8I', b, off + 16)
    p = off + 48; C = dict(off=off, ox=ox, oz=oz, cell=cell, W=W, H=H, flags=flags, parts={})
    def take(name, count, width, dt='<f4'):
        nonlocal p
        a = np.frombuffer(b, dt, count * width, p).reshape(count, width) if width > 1 else np.frombuffer(b, dt, count, p)
        C['parts'][name] = (p, a.nbytes); p += a.nbytes
        return a
    C['tri'] = take('tri', ntri, 12).astype(np.float64).reshape(-1, 4, 3)
    C['box'] = take('box', nbox, 16).astype(np.float64)
    cy = take('cyl', ncyl, 12); C['cyl'] = cy.astype(np.float64); C['cyl_flat'] = cy.view('<u4')[:, 8].copy()
    C['seg'] = take('seg', nseg, 8).astype(np.float64)
    C['start'] = take('cellStart', W * H + 1, 1, '<u4').astype(np.int64)
    C['refs'] = take('refs', nref, 1, '<u4').astype(np.int64)
    C['end'] = p
    return C

# ---------------------------------------------------------------------------------------------------------- проверки
class Report:
    def __init__(self): self.err, self.warn = [], []
    def check(self, ok, msg, warn=False):
        if not ok: (self.warn if warn else self.err).append(msg)
        return ok

def exact_bounds(C):
    """точные xz-габариты: треугольник, ящик (проекция), цилиндр (плоские торцы) / капсула / сфера"""
    T = C['tri']; t = np.c_[T[:, :3, 0].min(1), T[:, :3, 2].min(1), T[:, :3, 0].max(1), T[:, :3, 2].max(1)]
    B = C['box']; A = B[:, 3:12].reshape(-1, 3, 3); h = B[:, 12:15]
    ex = (np.abs(A[:, :, 0]) * h).sum(1); ez = (np.abs(A[:, :, 2]) * h).sum(1)
    b = np.c_[B[:, 0] - ex, B[:, 2] - ez, B[:, 0] + ex, B[:, 2] + ez]
    Y = C['cyl']; a, r, hl, flat = Y[:, 3:6], Y[:, 6], Y[:, 7], C['cyl_flat'] == 1
    def ext(k):
        cap = np.abs(a[:, k]) * hl + r
        disk = np.abs(a[:, k]) * hl + r * np.sqrt(np.clip(1 - a[:, k] ** 2, 0, 1))
        return np.where(flat, disk, cap)
    c = np.c_[Y[:, 0] - ext(0), Y[:, 2] - ext(2), Y[:, 0] + ext(0), Y[:, 2] + ext(2)]
    return t, b, c

def seg_rect_dist(ax, az, bx, bz, x0, z0, x1, z1):
    """расстояние от отрезка до прямоугольников [x0,x1]x[z0,z1] (векторно по прямоугольникам)"""
    # 0, если отрезок пересекает прямоугольник; иначе минимум из: концы отрезка до прямоугольника, углы до отрезка
    def pt_rect(px, pz): return np.hypot(np.maximum(0, np.maximum(x0 - px, px - x1)), np.maximum(0, np.maximum(z0 - pz, pz - z1)))
    def pt_seg(px, pz):
        dx, dz = bx - ax, bz - az; L = dx * dx + dz * dz
        t = np.clip(((px - ax) * dx + (pz - az) * dz) / L, 0, 1) if L > 0 else 0
        return np.hypot(ax + t * dx - px, az + t * dz - pz)
    d = np.minimum(pt_rect(ax, az), pt_rect(bx, bz))
    for px, pz in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)): d = np.minimum(d, pt_seg(px, pz))
    # пересечение: отсечение отрезка по прямоугольнику
    t0, t1 = np.zeros_like(x0), np.ones_like(x0); dx, dz = bx - ax, bz - az
    for dd, a0, lo, hi in ((dx, ax, x0, x1), (dz, az, z0, z1)):
        if abs(dd) < 1e-12: t0 = np.where((a0 < lo) | (a0 > hi), 2.0, t0)
        else:
            u0, u1 = (lo - a0) / dd, (hi - a0) / dd
            t0, t1 = np.maximum(t0, np.minimum(u0, u1)), np.minimum(t1, np.maximum(u0, u1))
    return np.where(t0 <= t1, 0.0, d)

def validate(C, R):
    W, H, ox, oz, cell = C['W'], C['H'], C['ox'], C['oz'], C['cell']
    st, refs = C['start'], C['refs']; cnt = {k: len(C[k]) for k in TYPES}
    R.check(st[0] == 0 and st[-1] == len(refs) and (np.diff(st) >= 0).all(), 'cellStart: не монотонный или не сходится с nref')
    typ, idx = refs >> 29, refs & ((1 << 29) - 1)
    for k, name in enumerate(TYPES):
        m = typ == k; R.check(not m.any() or idx[m].max() < cnt[name], f'refs: индекс {name} за пределами')
    R.check((typ <= 3).all(), 'refs: неизвестный тип')
    cell_of = np.repeat(np.arange(W * H), np.diff(st))
    key = (cell_of << 31) | refs
    R.check(len(np.unique(key)) == len(key), 'refs: повтор ссылки в клетке', warn=True)
    have = np.sort(key)
    def need(cells, ref):   # все (клетка, ссылка) должны быть в have
        k = (cells.astype(np.int64) << 31) | ref
        pos = np.searchsorted(have, k); pos = np.minimum(pos, len(have) - 1)
        return have[pos] == k
    missing, extra = {}, {}
    for k, (name, bb) in enumerate(zip(('tri', 'box', 'cyl'), exact_bounds(C))):
        if not len(bb): continue
        gx0 = np.floor((bb[:, 0] - ox) / cell).astype(int); gz0 = np.floor((bb[:, 1] - oz) / cell).astype(int)
        gx1 = np.floor((bb[:, 2] - ox) / cell).astype(int); gz1 = np.floor((bb[:, 3] - oz) / cell).astype(int)
        R.check((gx0 >= 0).all() and (gz0 >= 0).all() and (gx1 < W).all() and (gz1 < H).all(), f'{name}: габарит вне сетки')
        nx, nz = gx1 - gx0 + 1, gz1 - gz0 + 1; n = nx * nz
        i = np.repeat(np.arange(len(bb)), n); j = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
        cells = (gz0[i] + j // nx[i]) * W + gx0[i] + j % nx[i]
        ok = need(cells, (k << 29) | i); missing[name] = int((~ok).sum())
        extra[name] = int((typ == k).sum() - ok.sum())
    S = C['seg']; miss = tot = 0; margin = 0.5
    for i, (ax, az, bx, bz) in enumerate(S[:, :4]):
        gx0 = int(np.floor((min(ax, bx) - margin - ox) / cell)); gx1 = int(np.floor((max(ax, bx) + margin - ox) / cell))
        gz0 = int(np.floor((min(az, bz) - margin - oz) / cell)); gz1 = int(np.floor((max(az, bz) + margin - oz) / cell))
        gx, gz = np.meshgrid(np.arange(max(gx0, 0), min(gx1, W - 1) + 1), np.arange(max(gz0, 0), min(gz1, H - 1) + 1))
        gx, gz = gx.ravel(), gz.ravel()
        d = seg_rect_dist(ax, az, bx, bz, ox + gx * cell, oz + gz * cell, ox + (gx + 1) * cell, oz + (gz + 1) * cell)
        cells = (gz * W + gx)[d <= margin - 1e-4]; tot += len(cells)
        miss += int((~need(cells, np.full(len(cells), (3 << 29) | i))).sum())
    missing['seg'] = miss; extra['seg'] = int((typ == 3).sum() - (tot - miss))
    for name in TYPES: R.check(missing[name] == 0, f'{name}: {missing[name]} клеток по габариту без ссылки')
    # геометрия
    T = C['tri']; n = T[:, 3]; cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); cl = np.linalg.norm(cr, axis=1)
    R.check(np.isfinite(T).all() and np.isfinite(C['box']).all() and np.isfinite(C['cyl']).all() and np.isfinite(S).all(), 'не конечные числа')
    R.check(np.abs(np.linalg.norm(n, axis=1) - 1).max() < 1e-4, 'tri: нормаль не единичная')
    R.check(((cr / cl[:, None]) * n).sum(1).min() > 0.999, 'tri: нормаль не совпадает с cross(b-a, c-a)')
    R.check((n[:, 1] >= -1e-6).all(), f'tri: n.y < 0 у {(n[:, 1] < -1e-6).sum()}')
    R.check(cl.min() >= 1e-4, 'tri: вырожденный треугольник', warn=True)
    B = C['box']; A = B[:, 3:12].reshape(-1, 3, 3)
    if len(B):
        G = np.einsum('nij,nkj->nik', A, A)
        R.check(np.abs(G - np.eye(3)).max() < 1e-4, f'box: оси не ортонормальны (макс. {np.abs(G - np.eye(3)).max():.1e})')
        R.check((np.linalg.det(A) > 0).all(), 'box: левая тройка осей', warn=True)
        R.check((B[:, 12:15] >= 0).all(), 'box: отрицательный полуразмер')
    Y = C['cyl']
    if len(Y):
        R.check(np.abs(np.linalg.norm(Y[:, 3:6], axis=1) - 1).max() < 1e-4, 'cyl: ось не единичная')
        R.check((Y[:, 6] > 0).all() and (Y[:, 7] >= 0).all(), 'cyl: r <= 0 или halfLen < 0')
        R.check(np.isin(C['cyl_flat'], (0, 1)).all(), 'cyl: flat не 0/1')
    if len(S):
        sn, d = S[:, 4:6], S[:, 2:4] - S[:, 0:2]
        R.check(np.abs(np.linalg.norm(sn, axis=1) - 1).max() < 1e-4, 'seg: нормаль не единичная')
        R.check((np.abs((sn * d).sum(1)) / np.maximum(np.linalg.norm(d, axis=1), 1e-9)).max() < 1e-3, 'seg: нормаль не перпендикулярна')
        R.check((S[:, 6] < S[:, 7]).all(), 'seg: y0 >= y1')
    return missing, extra

# ---------------------------------------------------------------------------------------------- растр и заливка
class Raster:
    def __init__(self, x0, z0, x1, z1, ppm):
        self.x0, self.z0, self.ppm = x0, z0, ppm
        self.w, self.h = int(np.ceil((x1 - x0) * ppm)), int(np.ceil((z1 - z0) * ppm))
    def px(self, x, z): return ((x - self.x0) * self.ppm, (z - self.z0) * self.ppm)
    def cell(self, x, z): return (np.floor((z - self.z0) * self.ppm).astype(int), np.floor((x - self.x0) * self.ppm).astype(int))

def label_fill(free, seed):
    """связная (4 соседа) область free, содержащая seed (row, col). Минимум меток по сериям строк/столбцов + прыжки."""
    H, W = free.shape
    lab = np.where(free, np.arange(H * W).reshape(H, W), -1).astype(np.int64)
    def runmin(L, F):   # по строкам: в каждой непрерывной серии свободных клеток — минимум метки
        f = F.ravel(); l = L.ravel(); idx = np.flatnonzero(f)
        if not len(idx): return
        st = np.ones(len(idx), bool); st[1:] = (np.diff(idx) != 1) | (idx[1:] % F.shape[1] == 0)
        s = np.flatnonzero(st); m = np.minimum.reduceat(l[idx], s)
        l[idx] = np.repeat(m, np.diff(np.r_[s, len(idx)]))
    for _ in range(2000):
        old = lab.copy()
        runmin(lab, free)
        t = np.ascontiguousarray(lab.T); runmin(t, np.ascontiguousarray(free.T)); lab = np.ascontiguousarray(t.T)
        fl = lab.ravel(); m = fl >= 0
        for _ in range(3): fl[m] = fl[fl[m]]
        if np.array_equal(lab, old): break
    return lab == lab[seed] if free[seed] else np.zeros_like(free)

def fence_check(C, L, ppm=2.0, off=1.5):
    """заливка от спавна: по проходимой земле, заборы — стены (толщина ~1 м). Проверка сторон нормалей."""
    T, S = C['tri'], C['seg']
    walk = T[:, 3, 1] > WALK_NY
    x0, z0 = C['ox'], C['oz']; x1, z1 = x0 + C['W'] * C['cell'], z0 + C['H'] * C['cell']
    r = Raster(x0, z0, x1, z1, ppm)
    ground = Image.new('1', (r.w, r.h), 0); d = ImageDraw.Draw(ground)
    for t in T[walk]: d.polygon([r.px(v[0], v[2]) for v in t[:3]], fill=1)
    fence = Image.new('1', (r.w, r.h), 0); d = ImageDraw.Draw(fence)
    for s in S: d.line([r.px(s[0], s[1]), r.px(s[2], s[3])], fill=1, width=2)
    g, f = np.asarray(ground, bool), np.asarray(fence, bool)
    sx, _, sz = L['spawn']; seed = r.cell(np.array(sx), np.array(sz)); seed = (int(seed[0]), int(seed[1]))
    reach = label_fill(g & ~f, seed)
    # стороны каждого забора: точки на расстоянии off по нормали и против, в 3 местах вдоль
    res = {'ok': 0, 'wrong': 0, 'both': 0, 'none': 0}; wrong = []
    for i, s in enumerate(S):
        a, b, n = s[0:2], s[2:4], s[4:6]; L_ = np.linalg.norm(b - a)
        ts = (0.5,) if L_ < 2 else (0.25, 0.5, 0.75)
        side = []
        for sg in (1, -1):
            hit = False
            for t in ts:
                p = a + (b - a) * t + sg * n * off; rr, cc = r.cell(p[0], p[1])
                if 0 <= rr < r.h and 0 <= cc < r.w and reach[rr, cc]: hit = True
            side.append(hit)
        k = 'both' if all(side) else 'ok' if side[0] else 'wrong' if side[1] else 'none'
        res[k] += 1
        if k == 'wrong': wrong.append(i)
    # замкнутость: заливка без земли (только заборы — стены) не должна дойти до края
    free = ~f; free[0, :] = free[-1, :] = True; free[:, 0] = free[:, -1] = True
    open_ = label_fill(free, seed)
    leak = bool(open_[0, :].any() or open_[-1, :].any() or open_[:, 0].any() or open_[:, -1].any())
    return dict(res=res, wrong=wrong, reach=reach, raster=r, reach_m2=float(reach.sum() / ppm ** 2),
                ground_m2=float(g.sum() / ppm ** 2), leak=leak, enclosed_m2=float(open_.sum() / ppm ** 2))

# ----------------------------------------------------------------------------------------- геометрия отрисовки
def render_geometry(b, L, far=True):
    """-> вершины (N,3) и треугольники (M,3,3) кусков города (owner 0); far=True — дальняя версия (исходные треуг.)"""
    recs = np.frombuffer(b, np.dtype([('lo', '<f4', 3), ('hi', '<f4', 3), ('tex', '<i4'), ('fl', '<u4'), ('nv', '<u4'),
                                      ('ni', '<u4'), ('owner', '<u4'), ('c', '<f4', 3), ('S', '<f4'), ('off', '<u4'),
                                      ('nf', '<u4'), ('cell', '<u4'), ('pad', 'V8')]), L['npieces'], L['table'])
    cells = np.frombuffer(b, np.dtype([('lo', '<f4', 3), ('hi', '<f4', 3), ('first', '<u4'), ('n', '<u4'), ('owner', '<u4'),
                                       ('off', '<u4'), ('size', '<u4'), ('pad', 'V4')]), L['ncell'], L['cells'])
    V, TT = [], []
    for p in recs:
        if p['owner'] != 0: continue
        base = int(cells[p['cell']]['off']) + int(p['off'])
        q = np.frombuffer(b, QV, int(p['nv']), base)
        P = p['c'].astype(np.float64) + np.stack([q['x'], q['y'], q['z']], 1) * (float(p['S']) / 32768)
        o = base + ((int(p['nv']) * 16 + 15) & ~15); ni = int(p['ni'])
        if far:
            o += (ni * 2 + 15) & ~15; ii = np.frombuffer(b, '<u2', int(p['nf']), o)
        else: ii = np.frombuffer(b, '<u2', ni, o)
        V.append(P); TT.append(P[ii].reshape(-1, 3, 3))
    return np.concatenate(V), np.concatenate(TT)

def grid_hash(P, cell=4.0):
    k = np.floor(P[:, [0, 2]] / cell).astype(np.int64); key = k[:, 0] * 100003 + k[:, 1]
    o = np.argsort(key); key = key[o]; u, s = np.unique(key, return_index=True)
    return dict(cell=cell, P=P[o], keys=u, start=np.r_[s, len(key)])

def near_points(G, x0, z0, x1, z1):
    c = G['cell']; out = []
    for gx in range(int(np.floor(x0 / c)), int(np.floor(x1 / c)) + 1):
        ks = gx * 100003 + np.arange(int(np.floor(z0 / c)), int(np.floor(z1 / c)) + 1)
        i = np.searchsorted(G['keys'], ks); ok = (i < len(G['keys'])) & (G['keys'][np.minimum(i, len(G['keys']) - 1)] == ks)
        for j in i[ok]: out.append(G['P'][G['start'][j]:G['start'][j + 1]])
    return np.concatenate(out) if out else np.zeros((0, 3))

def alignment(C, V, pad=0.25):
    """доля ящиков/капсул, внутри которых (с запасом pad) есть вершины отрисовки; для земли — медиана расстояния от
    центра треугольника до ближайшей вершины. Второе число — если бы z у коллизии был отзеркален наоборот."""
    G = grid_hash(V); out = {}
    for flip in (False, True):
        s = -1 if flip else 1
        B = C['box'].copy(); B[:, [2, 5, 8, 11]] *= s
        hit = 0
        for bx in B:
            c, A, h = bx[0:3], bx[3:12].reshape(3, 3), bx[12:15] + pad; e = np.abs(A).T @ h
            P = near_points(G, c[0] - e[0], c[2] - e[2], c[0] + e[0], c[2] + e[2])
            if len(P) and (np.abs((P - c) @ A.T) <= h).all(1).any(): hit += 1
        Y = C['cyl'].copy(); Y[:, [2, 5]] *= s; hc = 0
        for cy in Y:
            c, a, r, hl = cy[0:3], cy[3:6], cy[6] + pad, cy[7]
            P = near_points(G, c[0] - hl - r, c[2] - hl - r, c[0] + hl + r, c[2] + hl + r)
            if not len(P): continue
            t = np.clip((P - c) @ a, -hl, hl); dd = np.linalg.norm(P - c - t[:, None] * a, axis=1)
            if (dd <= r).any(): hc += 1
        T = C['tri'][::max(1, len(C['tri']) // 3000)]; cen = T[:, :3].mean(1); cen[:, 2] *= s; dist = []
        for p in cen:
            P = near_points(G, p[0] - 4, p[2] - 4, p[0] + 4, p[2] + 4)
            dist.append(np.linalg.norm(P - p, axis=1).min() if len(P) else 99.0)
        out['flip' if flip else 'ok'] = (hit / max(1, len(B)), hc / max(1, len(Y)), float(np.median(dist)))
    return out

# ------------------------------------------------------------------------------------------------------ картинка
def draw_map(C, L, fc, T_render, window, ppm, path):
    x0, z0, x1, z1 = window; r = Raster(x0, z0, x1, z1, ppm)
    img = Image.new('RGB', (r.w, r.h), (14, 14, 18)); d = ImageDraw.Draw(img, 'RGBA')
    def inwin(xs, zs, m=2): return (xs.max() >= x0 - m) & (xs.min() <= x1 + m) & (zs.max() >= z0 - m) & (zs.min() <= z1 + m)
    T = C['tri']; ys = T[:, :3, 1].mean(1); lo, hi = np.percentile(ys, [1, 99])
    for t, y in zip(T, ys):
        if not inwin(t[:3, 0], t[:3, 2]): continue
        pts = [r.px(v[0], v[2]) for v in t[:3]]
        if t[3, 1] > WALK_NY:
            g = int(45 + 85 * np.clip((y - lo) / (hi - lo + 1e-9), 0, 1)); d.polygon(pts, fill=(g, g, g + 6))
    # залитая от спавна область
    if fc is not None:
        rr = fc['raster']; m = np.asarray(Image.fromarray((fc['reach'] * 255).astype(np.uint8)).resize(
            (int(round(rr.w * ppm / rr.ppm)), int(round(rr.h * ppm / rr.ppm))), Image.NEAREST))
        ox_, oz_ = int(round((rr.x0 - x0) * ppm)), int(round((rr.z0 - z0) * ppm))
        a = np.zeros((r.h, r.w), np.uint8)
        ys0, xs0 = max(0, oz_), max(0, ox_); ys1, xs1 = min(r.h, oz_ + m.shape[0]), min(r.w, ox_ + m.shape[1])
        if ys1 > ys0 and xs1 > xs0: a[ys0:ys1, xs0:xs1] = m[ys0 - oz_:ys1 - oz_, xs0 - ox_:xs1 - ox_] // 6
        blue = Image.new('RGBA', img.size, (70, 110, 255, 0)); blue.putalpha(Image.fromarray(a))
        img.paste(blue, (0, 0), blue); d = ImageDraw.Draw(img, 'RGBA')
    # стены отрисовки (крутые треугольники кусков города) — светло-серый
    if T_render is not None:
        n = np.cross(T_render[:, 1] - T_render[:, 0], T_render[:, 2] - T_render[:, 0])
        steep = np.abs(n[:, 1]) < 0.5 * np.linalg.norm(n, axis=1)
        for t in T_render[steep]:
            if inwin(t[:, 0], t[:, 2]): d.polygon([r.px(v[0], v[2]) for v in t], outline=(205, 205, 205, 150))
    for t in T:
        if t[3, 1] <= WALK_NY and inwin(t[:3, 0], t[:3, 2]):
            d.polygon([r.px(v[0], v[2]) for v in t[:3]], fill=(230, 40, 40), outline=(255, 60, 60))
    lw = max(1, int(ppm / 3))
    for bx in C['box']:
        c, A, h = bx[0:3], bx[3:12].reshape(3, 3), bx[12:15]
        corners = np.array([c + A.T @ (h * np.array(s)) for s in np.array(np.meshgrid([-1, 1], [-1, 1], [-1, 1])).T.reshape(-1, 3)])
        xz = corners[:, [0, 2]]
        if not inwin(xz[:, 0], xz[:, 1]): continue
        hull = convex_hull(xz); d.line([r.px(*p) for p in np.vstack([hull, hull[:1]])], fill=(70, 140, 255), width=lw)
    for cy in C['cyl']:
        c, a, rad, hl = cy[0:3], cy[3:6], cy[6], cy[7]
        if not inwin(np.array([c[0] - hl - rad, c[0] + hl + rad]), np.array([c[2] - hl - rad, c[2] + hl + rad])): continue
        e0, e1 = c - a * hl, c + a * hl
        for e in (e0, e1): d.ellipse([r.px(e[0] - rad, e[2] - rad), r.px(e[0] + rad, e[2] + rad)], outline=(60, 230, 90), width=lw)
        if hl * np.hypot(a[0], a[2]) > 0.05: d.line([r.px(e0[0], e0[2]), r.px(e1[0], e1[2])], fill=(60, 230, 90), width=lw)
    wrong = set(fc['wrong']) if fc else set()
    for i, s in enumerate(C['seg']):
        if not inwin(np.array([s[0], s[2]]), np.array([s[1], s[3]])): continue
        col = (255, 90, 0) if i in wrong else (255, 220, 0)
        d.line([r.px(s[0], s[1]), r.px(s[2], s[3])], fill=col, width=max(1, lw + 1))
        m = (s[0:2] + s[2:4]) / 2; tick = 3.0 if ppm < 4 else 1.5
        d.line([r.px(*m), r.px(*(m + s[4:6] * tick))], fill=(0, 230, 255), width=1)
    sx, _, sz = L['spawn']; hd = L['heading']; rad = max(4 / ppm, 1.5)
    d.ellipse([r.px(sx - rad, sz - rad), r.px(sx + rad, sz + rad)], fill=(255, 0, 255))
    # курс: как в движке (модель смотрит в -Z, рисуется с поворотом h+pi) — стрелка вдоль (sin h, cos h)
    d.line([r.px(sx, sz), r.px(sx + np.sin(hd) * rad * 4, sz + np.cos(hd) * rad * 4)], fill=(255, 0, 255), width=2)
    # масштаб 10 м
    d.line([(10, r.h - 12), (10 + 10 * ppm, r.h - 12)], fill=(255, 255, 255), width=2); d.text((12, r.h - 26), '10 m', fill=(255, 255, 255))
    img.save(path)
    return path

def convex_hull(P):
    P = sorted(map(tuple, np.round(P, 4)))
    if len(P) <= 2: return np.array(P)
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])

# ------------------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description='проверка COL1')
    ap.add_argument('shr'); ap.add_argument('--png'); ap.add_argument('--no-png', action='store_true')
    ap.add_argument('--crop', action='append', default=[], help='x,z,размер_м — ещё крупный план (6 px/м)')
    a = ap.parse_args()
    b, L = load(a.shr); C = parse_col(b, L['col']); R = Report()
    # место в файле
    R.check(C['end'] <= L['size'], 'COL1 выходит за конец файла')
    R.check(C['off'] % 16 == 0, 'COL1 не выровнена на 16')
    resident = L['cells'] + 48 * L['ncell']
    R.check(C['off'] >= resident, 'COL1 внутри резидентной части (перед таблицей клеток)')
    if L['pvs']:
        R.check(b[L['pvs']:L['pvs'] + 4] == b'PVS1', '@88 указывает не на PVS1')
        R.check(C['end'] <= L['pvs'], 'COL1 пересекается с PVS (должна лежать до неё)')
    print(f'{Path(a.shr).name}: {L["size"] / 2**20:.2f} MB, COL1 @{C["off"]:,}, PVS @{L["pvs"]:,}'
          + (' (нет)' if not L['pvs'] else '') + f', резидентная часть {resident / 2**20:.2f} MB')
    print(f'  сетка {C["W"]}x{C["H"]} по {C["cell"]:g} м от ({C["ox"]:g}, {C["oz"]:g}), flags {C["flags"]}')
    tot = 48
    for name, (off, nb) in C['parts'].items():
        n = {'tri': len(C['tri']), 'box': len(C['box']), 'cyl': len(C['cyl']), 'seg': len(C['seg']),
             'cellStart': len(C['start']), 'refs': len(C['refs'])}[name]
        print(f'  {name:9s} {n:8,d} шт. {nb / 1024:8.1f} KB'); tot += nb
    print(f'  всего {tot / 2**20:.2f} MB')
    T = C['tri']; walk = T[:, 3, 1] > WALK_NY
    print(f'  земля: проходимых {walk.sum():,}, крутых (n.y <= {WALK_NY}) {(~walk).sum():,}; '
          f'цилиндров с плоскими торцами {(C["cyl_flat"] == 1).sum()}, капсул {((C["cyl_flat"] == 0) & (C["cyl"][:, 7] > 0)).sum()}, '
          f'сфер {((C["cyl_flat"] == 0) & (C["cyl"][:, 7] == 0)).sum()}; ящиков с нулевым полуразмером {(C["box"][:, 12:15].min(1) <= 0).sum()}')
    per = np.diff(C['start']); ne = per[per > 0]; typ = C['refs'] >> 29
    cell_of = np.repeat(np.arange(len(per)), per)
    print(f'  ссылок {len(C["refs"]):,}: ' + ', '.join(f'{TYPES[k]} {int((typ == k).sum()):,}' for k in range(4))
          + f'; на непустую клетку ср. {ne.mean():.1f}, медиана {np.median(ne):.0f}, 99% {np.percentile(ne, 99):.0f}, макс {per.max()}'
          + f'; непустых {len(ne):,} из {len(per):,}')
    for k in range(4):
        pk = np.bincount(cell_of[typ == k], minlength=len(per)); nz = pk[pk > 0]
        if len(nz): print(f'    {TYPES[k]}: в клетке ср. {nz.mean():.1f}, макс {pk.max()}')
    # машина ~ 2x4.6 м: в худшем случае задевает 2x3 клетки — сколько примитивов проверять
    Wc = C['W']; pm = per.reshape(C['H'], Wc).astype(np.int64); s3 = np.zeros_like(pm)
    for dz in range(3):
        for dx in range(2): s3[:C['H'] - 2, :Wc - 1] += pm[dz:C['H'] - 2 + dz, dx:Wc - 1 + dx]
    print(f'  окно 2x3 клетки (машина): ссылок макс {s3.max()}, 99% {np.percentile(s3[s3 > 0], 99):.0f}')
    missing, extra = validate(C, R)
    print('  габарит -> клетки: ' + ', '.join(f'{k} пропусков {missing[k]}, лишних {extra[k]}' for k in TYPES))
    fc = fence_check(C, L)
    encl = 'утекла за край' if fc['leak'] else f'{fc["enclosed_m2"] / 1e6:.3f} км²'
    print(f'  заборы: нормаль в сторону залитой от спавна земли {fc["res"]["ok"]}, наоборот {fc["res"]["wrong"]}, '
          f'обе стороны {fc["res"]["both"]}, ни одной {fc["res"]["none"]} (из {len(C["seg"])}); '
          f'залито {fc["reach_m2"] / 1e6:.3f} км² из {fc["ground_m2"] / 1e6:.3f} км² проходимой земли; '
          f'заборы {"НЕ " if fc["leak"] else ""}замыкают мир (заливка без земли: {encl})')
    if fc['wrong']: print('    наоборот:', fc['wrong'][:40])
    R.check(fc['res']['wrong'] == 0, f'заборы: {fc["res"]["wrong"]} нормалей смотрят от проезжей части', warn=True)
    V, TRn = render_geometry(b, L)
    al = alignment(C, V)
    print(f'  совпадение с отрисовкой ({len(V):,} вершин): ящиков с вершинами внутри {al["ok"][0]:.1%} '
          f'(с обратным зеркалом {al["flip"][0]:.1%}), капсул {al["ok"][1]:.1%} ({al["flip"][1]:.1%}), '
          f'земля: медиана до ближайшей вершины {al["ok"][2]:.2f} м ({al["flip"][2]:.2f} м)')
    if not a.no_png:
        base = Path(a.png) if a.png else Path(a.shr).with_name(Path(a.shr).stem + '_col.png')
        x0, z0 = C['ox'], C['oz']; x1, z1 = x0 + C['W'] * C['cell'], z0 + C['H'] * C['cell']
        print('  карта:', draw_map(C, L, fc, TRn, (x0, z0, x1, z1), 2.0, base))
        sx, _, sz = L['spawn']
        crops = [('spawn', sx, sz, 160)] + [(f'crop{i}', *map(float, c.split(','))) for i, c in enumerate(a.crop)]
        for name, cx, cz, size in crops:
            p = base.with_name(base.stem + f'_{name}.png')
            print('  крупно:', draw_map(C, L, fc, TRn, (cx - size / 2, cz - size / 2, cx + size / 2, cz + size / 2), 6.0, p))
    for w in R.warn: print('  предупреждение:', w)
    for e in R.err: print('  ОШИБКА:', e)
    print('  итог:', 'ошибок нет' if not R.err else f'{len(R.err)} ошибок')
    return 1 if R.err else 0

if __name__ == '__main__':
    sys.exit(main())
