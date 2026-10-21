#!/usr/bin/env python3
"""Горизонт: плоские однотонные силуэты дальнего города (слово Роба 16.10: «фасады как в вестернах, силуэт дома, маяк виден издалека»).
Офлайн на Маке для точки обзора считаем верхнюю кромку всего, что дальше NEAR метров: для каждого азимута (бин 0,5°) максимальный угол места (tan).
Кромку упрощаем (Дуглас-Пекер) до нескольких десятков вершин: это контур-полигон, который на PSP рисуется лентой треугольников по цилиндру.
  horizon_export.py LEVEL.shr --view X,Z [--ey 3] [--near 200] [--far 1500] [--eps 0.004] [--png OUT.png]
Пока только расчёт и предпросмотр (панорама PNG); формат horizon.shr добавляется после принятия вида."""
import sys, argparse, struct, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read

NB = 720   # бинов по кругу
MAXNV = 300   # вершин контура на клетку не больше (движок принимает до 350)


def skyline(V, ex, ey, ez, near, far):
    dx = V[:, 0] - ex; dz = V[:, 2] - ez; d = np.hypot(dx, dz)
    m = (d >= near) & (d <= far)
    dx, dz, d, y = dx[m], dz[m], d[m], V[m, 1]
    az = (np.arctan2(dx, -dz) % (2 * np.pi)) / (2 * np.pi) * NB   # 0 = −Z (север), по часовой
    t = (y - ey) / d
    top = np.full(NB, -9.0); dist = np.zeros(NB)
    ib = np.minimum(az.astype(np.int64), NB - 1)
    np.maximum.at(top, ib, t)
    hit = np.nonzero(m)[0]
    # дистанция до самой высокой точки бина (для тона дымки)
    o = np.lexsort((t, ib)); last = np.append(np.nonzero(np.diff(ib[o]))[0], len(o) - 1)
    dist[ib[o][last]] = d[o][last]
    top[top < -8] = np.nan
    return top, dist


def fill_gaps(top):
    ok = ~np.isnan(top)
    if not ok.any(): return np.zeros_like(top)
    x = np.arange(NB)
    return np.interp(x, np.concatenate([x[ok] - NB, x[ok], x[ok] + NB]), np.concatenate([top[ok]] * 3))


def rdp(pts, eps):
    if len(pts) < 3: return list(range(len(pts)))
    keep = [0, len(pts) - 1]; stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        p0, p1 = pts[a], pts[b]   # ошибка по вертикали (в tan): взгляд снизу вверх, поперечное смещение неважно
        dd = np.abs(pts[a + 1:b, 1] - (p0[1] + (p1[1] - p0[1]) * (pts[a + 1:b, 0] - p0[0]) / (p1[0] - p0[0] + 1e-12)))
        if len(dd) and dd.max() > eps:
            k = a + 1 + int(dd.argmax()); keep.append(k); stack += [(a, k), (k, b)]
    return sorted(keep)


SKY_TAN = 0.012   # небо несёт свой силуэт, если мешы неба поднимаются над глазом выше этого tan (≈0,7°)
SKY_DIL = 6       # расширение маски по азимуту, бинов (±3°)


def contour(V, ex, ez, near, far, eps, ey=None, Vs=None):
    if ey is None:
        nb = V[np.hypot(V[:, 0] - ex, V[:, 2] - ez) < 15]
        ey = (float(np.median(nb[:, 1])) if len(nb) else 0.) + 2.
    top, dist = skyline(V, ex, ey, ez, near, far)
    sk = fill_gaps(top)
    if Vs is not None and len(Vs):
        # мешы неба (FL бит 1: слой дальнего вида уровня, движок рисует его последним) уже несут дальний силуэт, как и у оригинала (кадр PS2 L2): лента там не нужна и закрыла бы его.
        # На азимутах, где небо поднимается над глазом, лента опускается ниже горизонта (невидима)
        st, _ = skyline(Vs, ex, ey, ez, 0., 3000.)
        has = np.nan_to_num(st, nan=-9.) > SKY_TAN
        m = np.convolve(np.r_[has[-SKY_DIL:], has, has[:SKY_DIL]].astype(float), np.ones(2 * SKY_DIL + 1), 'valid') > 0
        sk = np.where(m, np.minimum(sk, -0.02), sk)
    pts = np.stack([np.arange(NB) / NB * 2 * np.pi, sk], 1); e = eps
    ids = rdp(pts, e)
    while len(ids) > MAXNV: e *= 1.3; ids = rdp(pts, e)   # потолок вершин на клетку: буфер ленты движка (horizon.h HZ_MAXV / 4)
    return ey, sk, ids, (~np.isnan(top)).mean()


def extract_landmark(V, x, z, r):
    """Ориентир (маяк, башня, труба): профиль вращения. Вершины в радиусе r м от (x, z) выше земли у основания; ось уточняется по середине высоты; для каждого метра высоты — макс. радиус.
    Возвращает (cx, cz, y0, H, [(радиус, высота), ...]) — правая половина контура сверху вниз-вверх не нужна, зеркалится при рисовании."""
    m = np.hypot(V[:, 0] - x, V[:, 2] - z) < r
    W = V[m]
    if len(W) < 8: return None
    y0 = float(np.percentile(W[:, 1], 5)); top = float(W[:, 1].max()); H = top - y0
    mid = W[(W[:, 1] > y0 + 0.3 * H) & (W[:, 1] < y0 + 0.9 * H)]
    cx, cz = (float(mid[:, 0].mean()), float(mid[:, 2].mean())) if len(mid) else (x, z)
    rad = np.hypot(W[:, 0] - cx, W[:, 2] - cz); h = W[:, 1] - y0
    nb = int(np.ceil(H)) + 1; prof = np.zeros(nb)
    np.maximum.at(prof, np.clip(h.astype(int), 0, nb - 1), rad)
    prof = np.maximum(prof, 0.3)
    pts = np.stack([np.arange(nb, dtype=float), prof], 1)
    ids = rdp(pts, 0.4)   # ошибка профиля по радиусу 0,4 м
    return cx, cz, y0, H, [(float(prof[i]), float(i)) for i in ids]


def write_hor1(path, V, cells, near, far, eps, radius, lms=(), Vs=None, gfn=None):
    """HOR1: 'HOR1', ncells u32, radius f32, nlm u32, смещение таблицы ориентиров u32, 12 нулей | ячейки по 32 Б: cx, cz, ey f32, nv u32, off u32, 12 нулей | вершины контура 4 Б: az u16 (0..65535 = 0..360°), tan s16 (/16384)"""
    tab = []; blob = bytearray()
    for (cx, cz) in cells:
        ey, sk, ids, cov = contour(V, cx, cz, near, far, eps, Vs=Vs)
        if cov < 0.05: continue
        off = len(blob)
        for i in ids:
            az = int(round(i / NB * 65536)) & 0xffff if i < NB else 65535
            blob += struct.pack('<Hh', az, int(np.clip(round(sk[i] * 16384), -32768, 32767)))
        tab.append((cx, cz, ey, len(ids), off, gfn(cx, cz) if gfn else 0))
    base = 32 + 32 * len(tab)
    out = bytearray(struct.pack('<4sIfII', b'HOR1', len(tab), radius, len(lms), base + len(blob)) + b'\0' * 12)   # +16: смещение таблицы ориентиров
    for (cx, cz, ey, nv, off, g) in tab: out += struct.pack('<3fIII8x', cx, cz, ey, nv, base + off, g)   # p0 = цвет дальней земли 0x00BBGGRR (0 — нет данных): земля ленты неотличима от земли рядом
    out += blob
    # ориентиры: таблица по 32 Б (cx, cz, y0, H f32, npts u32, off u32, 8 нулей), затем профили: (радиус см u16, высота см u16)
    lbase = len(out) + 32 * len(lms); lblob = bytearray(); ltab = bytearray()
    for (cx, cz, y0, H, prof) in lms:
        ltab += struct.pack('<4fII8x', cx, cz, y0, H, len(prof), lbase + len(lblob))
        for (rr, hh) in prof: lblob += struct.pack('<HH', min(65535, int(round(rr * 100))), min(65535, int(round(hh * 100))))
    out += ltab + lblob; Path(path).write_bytes(bytes(out))
    print('HOR1: ячеек', len(tab), 'ориентиров', len(lms), 'байт', len(out)); return tab


def ground_fn(level, d, keep):
    """средний цвет горизонтальных поверхностей (земля, дорога, газон) в кольце 120-450 м от клетки: ниже линии горизонта лента берёт его вместо цвета дымки"""
    import hlod_export
    tc = hlod_export.tex_avg_colors(level)
    P = d['P'][keep]; T = d['TEX'][keep]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); ar = np.linalg.norm(n, axis=1) + 1e-9
    hor = (np.abs(n[:, 1]) / ar > 0.9) & (ar > 0.5)
    c = P[hor].mean(1); w = ar[hor] * 0.5; col = tc[np.clip(T[hor], 0, len(tc) - 1)]
    def f(cx, cz):
        r = np.hypot(c[:, 0] - cx, c[:, 2] - cz); m = (r > 120) & (r < 450)
        if m.sum() < 20: return 0
        rgb = (col[m] * w[m, None]).sum(0) / w[m].sum()
        r_, g_, b_ = [int(np.clip(round(v), 1, 255)) for v in rgb]
        return (b_ << 16) | (g_ << 8) | r_
    return f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level')
    ap.add_argument('--view'); ap.add_argument('--out', help='записать horizon.shr (HOR1) по сетке клеток'); ap.add_argument('--cell', type=float, default=150.); ap.add_argument('--lvl', type=int, default=0); ap.add_argument('--lmfile', default=str(Path(__file__).resolve().parent / 'horizon_landmarks.json')); ap.add_argument('--radius', type=float, default=260.); ap.add_argument('--ey', type=float, default=None, help='высота глаза, м; по умолчанию земля под точкой (медиана вершин в 15 м) + 2')
    ap.add_argument('--near', type=float, default=200.); ap.add_argument('--far', type=float, default=1500.)
    ap.add_argument('--eps', type=float, default=0.004); ap.add_argument('--png'); ap.add_argument('--nosky', action='store_true', help='без учёта мешей неба (прежнее: лента поверх неба)')
    a = ap.parse_args()
    d = shr7read.load(a.level, far=False, owner=0)
    keep = (d['FL'] & (1 | 2 | 4)) == 0   # без полупрозрачных и неба
    skym = (d['FL'] & 1) != 0
    Vs = None if a.nosky else (np.concatenate([d['P'][skym].reshape(-1, 3), d['P'][skym].mean(1)]) if skym.any() else None)
    V = d['P'][keep].reshape(-1, 3)
    V = np.concatenate([V, d['P'][keep].mean(1)])   # центры треугольников: крупные грани не теряют кромку
    lms = []
    if a.out and a.lvl and Path(a.lmfile).exists():
        for (lx, lz, lr) in json.loads(Path(a.lmfile).read_text()).get(str(a.lvl), []):
            r = extract_landmark(V, lx, lz, lr)
            if r: lms.append(r); print('ориентир', (lx, lz), '->', 'ось %.1f,%.1f основание %.1f высота %.1f точек профиля %d' % (r[0], r[1], r[2], r[3], len(r[4])))
            # из панорамы вырезаем геометрию ориентира: он рисуется отдельной карточкой в своих координатах (параллакс клетки не двигает его)
            V = V[~((np.hypot(V[:, 0] - lx, V[:, 2] - lz) < max(lr, 14.)) & (V[:, 1] > (r[2] + 1.0 if r else -1e9)))]   # вырез шире профильного радиуса: рядом пристройки и остров
    if a.out:
        mn = V.min(0); mx = V.max(0)
        xs = np.arange(np.floor(mn[0] / a.cell) * a.cell + a.cell / 2, mx[0], a.cell); zs = np.arange(np.floor(mn[2] / a.cell) * a.cell + a.cell / 2, mx[2], a.cell)
        gfn = ground_fn(a.level, d, keep)
        write_hor1(a.out, V, [(float(x), float(z)) for x in xs for z in zs], a.near, a.far, a.eps, a.radius, lms, Vs, gfn); return
    ex, ez = [float(s) for s in a.view.split(',')]
    if a.ey is None:
        nb = V[np.hypot(V[:, 0] - ex, V[:, 2] - ez) < 15]
        a.ey = (float(np.median(nb[:, 1])) if len(nb) else 0.) + 2.
    print('глаз y %.1f' % a.ey)
    top, dist = skyline(V, ex, a.ey, ez, a.near, a.far)
    cover = (~np.isnan(top)).mean()
    sk = fill_gaps(top)
    pts = np.stack([np.arange(NB) / NB * 360.0 * (np.pi / 180), sk], 1)   # x радианы, y tan: eps в тех же единицах
    ids = rdp(np.stack([pts[:, 0], pts[:, 1]], 1), a.eps)
    print('точка', ex, ez, 'покрытие азимутов %.0f%%' % (cover * 100), 'вершин контура', len(ids), 'макс tan %.3f' % sk.max())
    if a.png:
        from PIL import Image, ImageDraw
        W, H = 1440, 360; im = Image.new('RGB', (W, H), (190, 205, 215)); dr = ImageDraw.Draw(im)
        sc = H * 0.9 / max(0.25, sk.max() * 1.1)
        poly = [(pts[i, 0] / (2 * np.pi) * W, H - sk_i * sc - 40) for i, sk_i in zip(ids, sk[ids])]
        dr.polygon([(0, H)] + poly + [(W, H)], fill=(96, 108, 118))
        dr.line([(0, H - 40), (W, H - 40)], fill=(255, 255, 255))
        Path(a.png).parent.mkdir(parents=True, exist_ok=True); im.save(a.png)


if __name__ == '__main__':
    main()
