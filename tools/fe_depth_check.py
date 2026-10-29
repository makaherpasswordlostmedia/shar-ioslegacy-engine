#!/usr/bin/env python3
"""Гейт правки Роба 133 («NEW GAME: на мгновение пол становится прозрачным»): глубина перелётов главного меню, fe.shr.

  python tools/fe_depth_check.py build/fe.shr [--step 0.5] [--grid 48x27]

Своя лучевая проверка по данным ФАЙЛА (куски s16 после нарезки, дорожки узлов и видимости, камера по кадрам — как
движок viewer/frontend3d.c: между кадрами данных линейно). Для каждого перелёта из таблицы FLT1 (туда и обратно),
шаг 0.5 кадра таймлайна, сетка лучей 48x27 через кадр 16:9:
  (а) драка глубины: пикселей, где ближайший непрозрачный кусок и следующий ЗА ним кусок другой текстуры ближе 4 единиц
      16-битной глубины PSP (шаг d^2/(65535*near), шум float24 ~±2 ед. с каждой стороны, docs/psp_tricks.md §4), — не
      больше, чем в главном виде (кадр меню, near 0.1 / far 100 — норма, которую Роб видит всё время: ~1%, в основном
      дальнее за окном) плюс 1.5 п.п. На старом файле (near 0.01 из данных) NEW GAME кадр 32 — 7.4%, перелёты с near
      из данных 0.1 — до 2%;
  (б) ближняя плоскость ничего не срезает: ближайшее попадание луча (любой кусок) по оси камеры >= near кадра.
Гомер (CHR1) и билборды не участвуют. Итог: строка OK/FAIL; код возврата 0/1.
"""
import argparse, math, struct, sys
from pathlib import Path
import numpy as np

F_BLEND, F_ADD, F_NOZW = 2, 4, 8
TR_TIMELINE = 2
VT = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')])
GAP, FIGHT_OVER = 4., .015   # порог (а): доля кадра меню + 1.5 п.п.


def load(path):
    b = Path(path).read_bytes()
    npc, opc, ntr, otr = struct.unpack_from('<4I', b, 20)
    nfr, ocam = struct.unpack_from('<2I', b, 44)
    cams = np.frombuffer(b, '<f4', nfr * 12, ocam).reshape(-1, 12).astype(np.float64)
    trs = [struct.unpack_from('<IIfII', b, otr + 32 * i) for i in range(ntr)]
    pcs = []
    for i in range(npc):
        p = struct.unpack_from('<6H2I4f', b, opc + 64 * i)
        fl, node, vis, nv, ov = p[2], p[3], p[4], p[6], p[7]
        q = np.frombuffer(b, VT, nv, ov)
        P = np.c_[q['x'], q['y'], q['z']].astype(np.float64) / 32768. * p[11] + np.array(p[8:11])
        pcs.append((P.reshape(-1, 3, 3), fl, node, vis, p[0]))
    assert b[-16:-12] == b'FLT1', 'в файле нет таблицы перелётов FLT1'
    off, n = struct.unpack_from('<II', b, len(b) - 12)
    fl_ = [struct.unpack_from('<BBHHHHHf', b, off + 16 * i) for i in range(n)]
    return b, cams, trs, pcs, fl_


def track_k(trs, ti, tl):
    typ, n, fps, fl, off = trs[ti]
    return off, (int(min(tl, n - 1)) if fl & TR_TIMELINE else 0)            # свои часы — кадр 0, как превью экспорта


def scene_at(b, trs, pcs, tl):
    """треугольники кадра tl -> (T (N,3,3), текстура куска, непрозрачный-пишет-глубину). Поверхность = текстура: куски
    одной текстуры (нарезка по клеткам, соседние треугольники) друг с другом не «дерутся»"""
    T, pid, opq = [], [], []
    for i, (P, fl, node, vis, tex) in enumerate(pcs):
        if vis != 0xffff:
            off, k = track_k(trs, vis, tl)
            if not b[off + k]: continue
        if node != 0xffff:
            off, k = track_k(trs, node, tl)
            M = np.frombuffer(b, '<f4', 12, off + 48 * k).reshape(3, 4).astype(np.float64); P = P @ M[:, :3].T + M[:, 3]
        T.append(P); pid.append(np.full(len(P), tex)); opq.append(np.full(len(P), not (fl & (F_BLEND | F_ADD | F_NOZW))))
    return np.concatenate(T), np.concatenate(pid), np.concatenate(opq)


def cam_at(cams, tl):
    f0 = int(tl); f1 = min(f0 + 1, len(cams) - 1); u = tl - f0
    return cams[f0] + (cams[f1] - cams[f0]) * u                           # движок: все 12 чисел линейно


def hits(T, c, GX, GY):
    """все попадания лучей сетки в треугольники: (пиксель, треугольник, глубина по оси камеры).
    Кандидаты — по прямоугольнику проекции треугольника в сетке (у пересекающих плоскость глаза — вся сетка)"""
    pos = c[0:3]; fwd = c[3:6] / np.linalg.norm(c[3:6]); r = np.cross(fwd, c[6:9]); r /= np.linalg.norm(r); u_ = np.cross(r, fwd)
    tv = math.tan(c[9] * .5) * .75; th = tv * 16. / 9.
    rel = T - pos; x = rel @ r; y = rel @ u_; z = rel @ fwd
    out = (np.all(x > z * th, 1) | np.all(-x > z * th, 1) | np.all(y > z * tv, 1) | np.all(-y > z * tv, 1) | np.all(z <= 0, 1))
    front = np.all(z > 1e-4, 1)
    zs = np.where(front[:, None], z, 1.)
    gx = (x / zs / th + 1) * .5 * GX - .5; gy = (1 - y / zs / tv) * .5 * GY - .5
    x0 = np.where(front, np.ceil(gx.min(1)), 0); x1 = np.where(front, np.floor(gx.max(1)), GX - 1)
    y0 = np.where(front, np.ceil(gy.min(1)), 0); y1 = np.where(front, np.floor(gy.max(1)), GY - 1)
    x0 = np.clip(x0, 0, GX - 1); x1 = np.clip(x1, 0, GX - 1); y0 = np.clip(y0, 0, GY - 1); y1 = np.clip(y1, 0, GY - 1)
    ok = ~out & (x1 >= x0) & (y1 >= y0)
    idx = np.where(ok)[0]; w = (x1[idx] - x0[idx] + 1).astype(np.int64); h = (y1[idx] - y0[idx] + 1).astype(np.int64)
    cnt = w * h; tot = int(cnt.sum())
    if not tot: return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    ti = np.repeat(idx, cnt); o = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    ww = np.repeat(w, cnt); px = x0[ti].astype(np.int64) + o % ww; py = y0[ti].astype(np.int64) + o // ww
    sx = (px + .5) / GX * 2 - 1; sy = 1 - (py + .5) / GY * 2
    D = fwd + r * (sx * th)[:, None] + u_ * (sy * tv)[:, None]; D /= np.linalg.norm(D, axis=1, keepdims=True)
    A = T[ti]; e1 = A[:, 1] - A[:, 0]; e2 = A[:, 2] - A[:, 0]
    pv = np.cross(D, e2); det = (e1 * pv).sum(1); good = np.abs(det) > 1e-12; inv = np.where(good, 1. / np.where(good, det, 1.), 0.)
    tvv = pos - A[:, 0]; uu = (tvv * pv).sum(1) * inv; q = np.cross(tvv, e1); vv = (D * q).sum(1) * inv; t = (e2 * q).sum(1) * inv
    m = good & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 1e-5)
    return (py * GX + px)[m], ti[m], (t * (D @ fwd))[m]


def zq(d, n, f):
    return 32767.5 - 32767.5 * ((f + n) / (f - n) - 2 * f * n / ((f - n) * d))


def frame_stats(b, cams, trs, pcs, tl, GX, GY):
    c = cam_at(cams, tl); n, f = c[10], c[11]
    T, pid, opq = scene_at(b, trs, pcs, tl)
    pix, ti, d = hits(T, c, GX, GY)
    nearest = float(d.min()) if len(d) else math.inf
    m = opq[ti]; pix, ti, d = pix[m], ti[m], d[m]
    if not len(d): return 0, 0, nearest, n
    o = np.lexsort((d, pix)); pix, ti, d = pix[o], ti[o], d[o]; pc = pid[ti]
    start = np.r_[0, np.where(np.diff(pix))[0] + 1]; g = np.repeat(np.arange(len(start)), np.diff(np.r_[start, len(pix)]))
    p0 = pc[start][g]; z0 = d[start]
    live = (z0 >= n) & (z0 <= f)
    cand = np.where(pc != p0, np.arange(len(pc)), len(pc))
    first = np.minimum.reduceat(cand, start)
    has = first < len(pc); z1 = np.where(has, d[np.minimum(first, len(pc) - 1)], np.inf)
    gap = zq(z0, n, f) - zq(np.minimum(z1, f), n, f)
    fights = int((live & has & (z1 <= f) & (gap < GAP)).sum())
    return fights, int(live.sum()), nearest, n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('fe'); ap.add_argument('--step', type=float, default=.5)
    ap.add_argument('--grid', default='48x27'); ap.add_argument('--frames', help='только эти кадры таймлайна (через запятую)')
    a = ap.parse_args(); GX, GY = map(int, a.grid.split('x'))
    b, cams, trs, pcs, fl = load(a.fe)
    spans = []
    for item, flags, _, g0, g1, b0, b1, _ang in fl:
        spans.append((item, 'туда', g0, g1))
        if flags & 1: spans.append((item, 'обратно', b0, b1))
    menu, = struct.unpack_from('<I', b, 52)
    fm, tm, _, _ = frame_stats(b, cams, trs, pcs, float(menu), GX, GY); base = fm / max(tm, 1); lim = base + FIGHT_OVER
    print(f'главный вид (кадр {menu}): драка глубины {base * 100:.2f}% -> порог перелётов {lim * 100:.2f}%')
    errs = []; worst_all = (0., None); ns = 0
    for item, way, s0, s1 in spans:
        tls = [float(x) for x in a.frames.split(',')] if a.frames else list(np.arange(s0, s1 + 1e-6, a.step))
        worst = (0., None); holes = []
        for tl in tls:
            if not (s0 <= tl <= s1): continue
            fights, tot, nearest, n = frame_stats(b, cams, trs, pcs, float(tl), GX, GY); ns += 1
            share = fights / max(tot, 1)
            if share > worst[0]: worst = (share, (float(tl), fights, tot, round(float(n), 4)))
            if nearest < n - 1e-6: holes.append((float(tl), round(nearest, 4), round(float(n), 4)))
        print(f'перелёт пункт {item} {way} {s0}→{s1}: драка глубины макс {worst[0] * 100:.2f}% {worst[1] or ""}'
              + (f'; срез ближней плоскостью: {len(holes)} кадров, первый {holes[0]}' if holes else ''))
        if worst[0] > lim: errs.append(f'пункт {item} {way}: драка глубины {worst[0] * 100:.1f}% (кадр {worst[1][0]})')
        if holes: errs.append(f'пункт {item} {way}: ближняя плоскость срезает (кадр {holes[0][0]})')
        if worst[0] > worst_all[0]: worst_all = worst
    print(('OK' if not errs else 'FAIL ' + '; '.join(errs)) + f' · fe_depth_check {Path(a.fe).name}: подкадров {ns}, '
          f'худшая драка {worst_all[0] * 100:.2f}%')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
