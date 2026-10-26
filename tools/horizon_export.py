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


def contour(V, ex, ez, near, far, eps, ey=None, Vs=None, C=None):
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
    dd = dist.copy(); okd = dd > 0   # №934 (HOR2): расстояние до точки контура по бинам (skyline), пустые азимуты — по соседям (как и высота)
    if okd.any(): x_ = np.arange(NB); dd = np.interp(x_, np.concatenate([x_[okd] - NB, x_[okd], x_[okd] + NB]), np.concatenate([dd[okd]] * 3))
    else: dd = np.full(NB, float(far))
    fc = facade_cols(V, C, ex, ey, ez, near, far, top) if C is not None else None   # №997
    return ey, sk, ids, (~np.isnan(top)).mean(), dd, fc


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
    # №928: профиль по шагу 2 м (не 1 м: ступеньки по метру давали полосатый силуэт), потолок 14 точек: цена ориентира в кадре — вершины.
    # №928 приёмка «Контур» (кадры бота на семи уровнях): радиус от оси до самой дальней вершины раздувал вытянутые дома (карточка шире настоящего здания в 1,5–2 раза у
    # 58 % ориентиров по среднему азимуту, у 83 % по худшему): карточка смотрит на камеру и рисуется одной шириной со всех сторон. Теперь ширина на каждой высоте — среднее
    # геометрическое наименьшей и наибольшей видимой ширины объекта по азимутам (окно ±1 шаг по высоте): против настоящего ≤ 1,5× на 100 % по среднему азимуту и на 91 % по худшему.
    # LM_PROF928_OLD=1 в окружении — прежний профиль (радиус до дальней вершины)
    import os
    STEP = 2.0; nb = int(np.ceil(H / STEP)) + 1; prof = np.zeros(nb); rel = np.stack([W[:, 0] - cx, W[:, 2] - cz], 1)
    if os.environ.get('LM_PROF928_OLD'):
        np.maximum.at(prof, np.clip((h / STEP).astype(int), 0, nb - 1), rad)
        prof = np.maximum(np.maximum(prof, np.r_[prof[1:], prof[-1]]), np.r_[prof[0], prof[:-1]])
    else:
        az = np.radians(np.arange(0, 180, 15)); U = np.stack([np.cos(az), -np.sin(az)], 1)
        for i in range(nb):
            s_ = (h >= i * STEP - STEP) & (h < i * STEP + STEP)
            if s_.sum() < 2: continue
            pr = rel[s_] @ U.T; w = np.maximum(pr.max(0) - pr.min(0), 0.6); prof[i] = np.sqrt(w.min() * w.max()) / 2
        have = np.where(prof > 0)[0]
        if len(have): prof = np.where(prof > 0, prof, np.interp(np.arange(nb), have, prof[have]))   # высоты без вершин — по соседям
    prof = np.maximum(prof, 0.3)
    pts = np.stack([np.arange(nb, dtype=float) * STEP, prof], 1)
    e = 0.8; ids = rdp(pts, e)
    while len(ids) > 14: e *= 1.3; ids = rdp(pts, e)
    return cx, cz, y0, H, [(float(prof[i]), float(i) * STEP) for i in ids]


DQ_BASE = 130.; DQ_STEP = 1.19   # шкала расстояний DST2: 130 · 1,19^k
def dq(d):
    return np.clip(np.round(np.log(np.maximum(np.asarray(d, float), DQ_BASE) / DQ_BASE) / np.log(DQ_STEP)), 0, 15).astype(np.uint8)
def pack4(a):
    a = np.asarray(a, np.uint8)
    if len(a) % 2: a = np.r_[a, 0].astype(np.uint8)
    return bytes((a[0::2] | (a[1::2] << 4)).astype(np.uint8).tobytes())


def facade_cols(V, C, ex, ey, ez, near, far, top, below=0.04, smooth=3):
    """№997: цвет фасада, дающего кромку: по бинам азимута среднее цвета точек не ниже top − below (tan, ≈2,3° под самой высокой точкой бина) на расстоянии near..far; цвет точки — средний цвет
    текстуры × вершинный цвет треугольника (свет запечён, приём tools/silh_export.py). Окно ±smooth бинов, пустые азимуты — по соседям. Возвращает (NB, 3) RGB 0..255."""
    dx = V[:, 0] - ex; dz = V[:, 2] - ez; d = np.hypot(dx, dz)
    m = (d >= near) & (d <= far)
    dx, dz, d, y, c = dx[m], dz[m], d[m], V[m, 1], C[m]
    az = (np.arctan2(dx, -dz) % (2 * np.pi)) / (2 * np.pi) * NB
    ib = np.minimum(az.astype(np.int64), NB - 1); t = (y - ey) / d
    tb = top[ib]; sel = t >= (np.nan_to_num(tb, nan=9.0) - below)
    sums = np.zeros((NB, 3)); cnt = np.zeros(NB)
    np.add.at(sums, ib[sel], c[sel]); np.add.at(cnt, ib[sel], 1.0)
    k = np.ones(2 * smooth + 1)
    def circ(v): return np.stack([np.convolve(np.r_[v[-smooth:, i], v[:, i], v[:smooth, i]], k, 'valid') for i in range(v.shape[1])], 1)
    sums = circ(np.c_[sums]); cnt = circ(cnt[:, None])[:, 0]
    ok = cnt > 0; out = np.full((NB, 3), 128.0)
    if ok.any():
        avg = sums[ok] / cnt[ok, None]; x = np.arange(NB)
        for i in range(3): out[:, i] = np.interp(x, np.concatenate([x[ok] - NB, x[ok], x[ok] + NB]), np.concatenate([avg[:, i]] * 3))
    return out


def tri_colors(level, d, keep):
    """№997: цвет каждого треугольника (после маски keep): средний цвет текстуры × средний вершинный цвет (байты +4..+6 вершины 16 Б; у 12-байтовой вершины цвета нет — 0,78)"""
    import hlod_export
    tc = hlod_export.tex_avg_colors(level); b = np.frombuffer(Path(level).read_bytes(), np.uint8)
    T = d['TEX'][keep]; OFF = d['OFF'][keep]; VS = d['VS'][keep]; vc = np.zeros((len(T), 3))
    for k in range(3):
        o = OFF + k * VS; vc += b[o[:, None] + np.arange(4, 7)[None, :]]
    vc = vc / 3.0 / 255.0; vc[VS != 16] = 0.78
    return tc[np.clip(T, 0, len(tc) - 1)] * vc


def palette16(cols, iters=14):
    """16 цветов по всем вершинам контуров (Ллойд, начало — равномерные квантили по яркости)"""
    X = np.asarray(cols, float); lum = X @ np.array([.3, .59, .11]); o = np.argsort(lum)
    Cc = X[o[(np.linspace(0, 1, 16) * (len(X) - 1)).astype(int)]].copy()
    for _ in range(iters):
        idx = ((X[:, None, :] - Cc[None]) ** 2).sum(2).argmin(1)
        for k in range(16):
            if (idx == k).any(): Cc[k] = X[idx == k].mean(0)
    idx = ((X[:, None, :] - Cc[None]) ** 2).sum(2).argmin(1)
    return np.clip(np.round(Cc), 0, 255).astype(np.uint8), idx.astype(np.uint8)


def write_hor1(path, V, cells, near, far, eps, radius, lms=(), Vs=None, gfn=None, near2=None, C=None, lmcols=None):
    """HOR1: 'HOR1', ncells u32, radius f32, nlm u32, смещение таблицы ориентиров u32, 12 нулей | ячейки по 32 Б: cx, cz, ey f32, nv u32, off u32, 12 нулей | вершины контура 4 Б: az u16 (0..65535 = 0..360°), tan s16 (/16384)"""
    tab = []; blob = bytearray(); dst = []; hcl = []   # dst: по две записи на клетку (основной контур, второй) — расстояния для DST1
    for (cx, cz) in cells:
        ey, sk, ids, cov, dd, fc = contour(V, cx, cz, near, far, eps, Vs=Vs, C=C)
        if cov < 0.05: continue
        hc0 = fc[np.minimum(ids, NB - 1)] if fc is not None else None; hc1 = None   # №997: цвета вершин контура
        dst.append(dq(dd[np.minimum(ids, NB - 1)])); dst2 = None
        off = len(blob)
        for i in ids:
            az = int(round(i / NB * 65536)) & 0xffff if i < NB else 65535
            blob += struct.pack('<Hh', az, int(np.clip(round(sk[i] * 16384), -32768, 32767)))
        off2 = nv2 = 0
        if near2:   # №913: второй контур клетки (от near2 м) — для зон, где город держится дальше; p1 = смещение, p2 = число вершин
            _, sk2, ids2, _, dd2, fc2 = contour(V, cx, cz, near2, far, eps, Vs=Vs, ey=ey, C=C)
            hc1 = fc2[np.minimum(ids2, NB - 1)] if fc2 is not None else None
            dst2 = dq(dd2[np.minimum(ids2, NB - 1)])
            off2 = len(blob); nv2 = len(ids2)
            for i in ids2:
                az = int(round(i / NB * 65536)) & 0xffff if i < NB else 65535
                blob += struct.pack('<Hh', az, int(np.clip(round(sk2[i] * 16384), -32768, 32767)))
        tab.append((cx, cz, ey, len(ids), off, gfn(cx, cz) if gfn else 0, off2, nv2)); dst.append(dst2 if dst2 is not None else np.zeros(0, np.uint8))
        hcl.append((hc0, hc1))
    base = 32 + 32 * len(tab)
    out = bytearray(struct.pack('<4sIfII', b'HOR1', len(tab), radius, len(lms), base + len(blob)) + b'\0' * 12)   # +16: смещение таблицы ориентиров
    for (cx, cz, ey, nv, off, g, off2, nv2) in tab: out += struct.pack('<3fIIIII', cx, cz, ey, nv, base + off, g, (base + off2) if nv2 else 0, nv2)   # p0 = цвет дальней земли 0x00BBGGRR (0 — нет данных): земля ленты неотличима от земли рядом
    out += blob
    # ориентиры: таблица по 32 Б (cx, cz, y0, H f32, npts u32, off u32, 8 нулей), затем профили: (радиус см u16, высота см u16)
    lbase = len(out) + 32 * len(lms); lblob = bytearray(); ltab = bytearray()
    for (cx, cz, y0, H, prof) in lms:
        ltab += struct.pack('<4fII8x', cx, cz, y0, H, len(prof), lbase + len(lblob))
        for (rr, hh) in prof: lblob += struct.pack('<HH', min(65535, int(round(rr * 100))), min(65535, int(round(hh * 100))))
    out += ltab + lblob
    # №934 HOR2: хвост DST2 — расстояние до точки контура на каждой вершине, 4 бита на вершину (шкала 130 м × 1,19^k, k = 0…15, до 1,77 км; ошибка расстояния ≤ 8,6 %: на клетке 60 м уводит точку с глаза не больше чем на 0,7°, а в центре клетки контур точный).
    # Движок ставит вершину в мировых координатах (cx + D sin a, ey + tan·D, cz − D cos a) и проецирует на цилиндр дальности с настоящего глаза (лента не прыгает при смене клетки на склоне: поправка высоты шла на радиусе 154 м, а дом стоит на D ≥ 300 м).
    # Четыре бита, а не байт: хвост 8 бит на вершину давал +21…60 КБ к horizon.shr (куча уровня хуже TEST59 на 0,04 МБ), 4 бита — вдвое меньше.
    # Формат: 'DST2', ncell u32, 8 нулей | u32 смещение массива клетки от начала хвоста × ncell | массивы (на клетку: ceil(nv/2) байт основного контура, затем ceil(p2/2) байт второго; младшая тетрада — чётная вершина) | добивка до 4 | подвал 16 Б 'DSTF', u32 смещение хвоста, 8 нулей
    # №997 HCL1: цвет фасада на каждой вершине контура (4 бита — номер цвета из палитры уровня на 16 цветов, как DST2), хвост ПЕРЕД DST2: смещение лежит в заголовке DST2 (байты 8..11, там были нули —
    # прежний движок их не читает и читает файл как раньше). Формат: 'HCL1', ncell u32, 8 нулей | палитра 16 × (r, g, b, 0) | u32 смещение массива клетки от начала хвоста × ncell | массивы (на клетку: ceil(nv/2) байт основного контура,
    # затем ceil(p2/2) байт второго; младшая тетрада — чётная вершина) | добивка до 4
    hcl_off = 0
    if C is not None and hcl:
        allc = np.concatenate([x for pr in hcl for x in pr if x is not None]); pal, _ = palette16(allc)
        def idxof(cv): return ((cv[:, None, :] - pal[None].astype(float)) ** 2).sum(2).argmin(1).astype(np.uint8)
        hcl_off = len(out); hh = bytearray(b'HCL1' + struct.pack('<I', len(tab)) + b'\0' * 8)
        for (r_, g_, b_) in pal: hh += bytes((int(r_), int(g_), int(b_), 0))
        cur = len(hh) + 4 * len(tab); offs = bytearray(); arrs = bytearray()
        for (h0_, h1_) in hcl:
            a0 = pack4(idxof(h0_)) if h0_ is not None else b''; a1 = pack4(idxof(h1_)) if h1_ is not None else b''
            offs += struct.pack('<I', cur); arrs += a0 + a1; cur += len(a0) + len(a1)
        arrs += b'\0' * (-len(arrs) % 4)
        lmb = b''.join(bytes((int(c[0]), int(c[1]), int(c[2]), 0)) for c in lmcols) if lmcols and len(lmcols) == len(lms) else b''   # цвет карточки каждого ориентира (r, g, b, 0), в порядке таблицы ориентиров
        if lmb: struct.pack_into('<I', hh, 8, hcl_off + len(hh) + len(offs) + len(arrs))   # заголовок HCL1, байты 8..11: смещение цветов ориентиров от начала файла (0 — нет)
        out += hh + offs + arrs + lmb
        print('HCL1: палитра', [tuple(int(v) for v in c) for c in pal][:16], 'байт', len(hh) + len(offs) + len(arrs) + len(lmb), 'цветов ориентиров', len(lmb) // 4)
    t0 = len(out); n_ = len(tab); hdr = bytearray(b'DST2' + struct.pack('<II', n_, hcl_off) + b'\0' * 4); arrs = bytearray(); cur = 16 + 4 * n_
    for i in range(n_):
        a0 = pack4(dst[2 * i]); a1 = pack4(dst[2 * i + 1]); hdr += struct.pack('<I', cur); arrs += a0 + a1; cur += len(a0) + len(a1)
    arrs += b'\0' * (-len(arrs) % 4)   # подвал 'DSTF' + смещение читаются как u32: хвост выровнен на 4 (PSP падает на невыровненном чтении, эмулятор прощает)
    out += hdr + arrs + b'DSTF' + struct.pack('<I', t0) + b'\0' * 8
    Path(path).write_bytes(bytes(out))
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
    ap.add_argument('--near2', type=float, default=0., help='второй контур клетки от этого радиуса (p1/p2 клетки HOR1): зоны 150 м при основном --near 130');
    ap.add_argument('--nocolor', action='store_true', help='№997: без хвоста HCL1 (цвета фасадов дальних домов)'); ap.add_argument('--near', type=float, default=200.); ap.add_argument('--far', type=float, default=1500.)
    ap.add_argument('--eps', type=float, default=0.004); ap.add_argument('--png'); ap.add_argument('--nosky', action='store_true', help='без учёта мешей неба (прежнее: лента поверх неба)')
    a = ap.parse_args()
    d = shr7read.load(a.level, far=False, owner=0)
    keep = (d['FL'] & (1 | 2 | 4)) == 0   # без полупрозрачных и неба
    skym = (d['FL'] & 1) != 0
    Vs = None if a.nosky else (np.concatenate([d['P'][skym].reshape(-1, 3), d['P'][skym].mean(1)]) if skym.any() else None)
    V = d['P'][keep].reshape(-1, 3)
    V = np.concatenate([V, d['P'][keep].mean(1)])   # центры треугольников: крупные грани не теряют кромку
    Cv = None
    if a.out and not a.nocolor:   # №997: цвет каждой точки V (вершины и центры треугольников) — средний цвет текстуры × свет вершин; режем вместе с V
        ct = tri_colors(a.level, d, keep); Cv = np.concatenate([np.repeat(ct, 3, axis=0), ct])
    lms = []; lmcols = []
    if a.out and a.lvl and Path(a.lmfile).exists():
        for (lx, lz, lr) in json.loads(Path(a.lmfile).read_text()).get(str(a.lvl), []):
            r = extract_landmark(V, lx, lz, lr)
            if r and Cv is not None:   # №997: цвет карточки ориентира — средний цвет его точек (текстура × свет) выше основания
                sel_ = (np.hypot(V[:, 0] - lx, V[:, 2] - lz) < max(lr, 14.)) & (V[:, 1] > r[2] + 1.0); lmcols.append(Cv[sel_].mean(0) if sel_.any() else np.array([128., 128., 128.]))
            if r: lms.append(r); print('ориентир', (lx, lz), '->', 'ось %.1f,%.1f основание %.1f высота %.1f точек профиля %d' % (r[0], r[1], r[2], r[3], len(r[4])))
            # из панорамы вырезаем геометрию ориентира: он рисуется отдельной карточкой в своих координатах (параллакс клетки не двигает его)
            cut_ = ~((np.hypot(V[:, 0] - lx, V[:, 2] - lz) < max(lr, 14.)) & (V[:, 1] > (r[2] + 1.0 if r else -1e9))); V = V[cut_]; Cv = Cv[cut_] if Cv is not None else None   # вырез шире профильного радиуса: рядом пристройки и остров
    if a.out:
        mn = V.min(0); mx = V.max(0)
        xs = np.arange(np.floor(mn[0] / a.cell) * a.cell + a.cell / 2, mx[0], a.cell); zs = np.arange(np.floor(mn[2] / a.cell) * a.cell + a.cell / 2, mx[2], a.cell)
        gfn = ground_fn(a.level, d, keep)
        write_hor1(a.out, V, [(float(x), float(z)) for x in xs for z in zs], a.near, a.far, a.eps, a.radius, lms, Vs, gfn, a.near2 or None, Cv, lmcols); return
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
