#!/usr/bin/env python3
"""Силуэты за дальностью (слово Роба 16.10: «дальше прорисовку: 200 м и хотя бы силуэты»; PS2: у оригинала своих LOD нет, дальние дома — настоящие меши).
Офлайн упрощение города одного уровня в маленький файл silh.shr (формат SIL1, viewer/silh.h):
  silh_export.py LEVEL.shr OUT.shr [--col 25] [--ground 50] [--block 100] [--minh 4]
Ящики по сетке 25 м (крыши/стены домов и холмов, соседние колонки одной высоты склеены вдоль X) + земля квадратами 50 м; цвет = средний цвет текстуры
куска × вершинный цвет (свет запечён), низ ящика темнее верха (градиент вместо стены света). Без текстур, всегда в памяти, цель <= 300 КБ.
Формат SIL1: 'SIL1', nblocks u32, block float, pad | блоки по 48 Б: cx, cz, y0, y1, half, 0, voff, nv, ioff, ni, 0, 0 | вершины 16 Б (ABGR u32, x, y, z float: x, z от центра блока,
y мировая) | индексы u16 (треугольники). Ящик 8 вершин / 30 индексов, земля 4 / 6."""
import sys, struct, argparse
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read


def tex_means(b):
    ntex, npc = struct.unpack_from('<II', b, 4)
    W, H = struct.unpack_from('<II', b, 68)
    p = 104 + W * H * 8; p += -p % 16; p += W * H * 4; p += -p % 16
    out = []
    for _ in range(ntex):
        w, h, lv = struct.unpack_from('<HHH', b, p); fmt, pre = b[p + 6], b[p + 7]
        pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4).astype(np.float64)
        q = p + 16 + 1024; bpp = 4 if fmt == 4 else 8; sw = 0; lw, lh = w, h; l0 = q
        sz0 = None
        for li in range(lv):
            rows = (lh + 7) & ~7 if pre else lh
            rb = max(16, (lw * bpp + 7) // 8) if pre else lw * bpp // 8
            if li == 0: sz0 = rb * rows
            q += rb * rows; q += -q % 16; lw >>= 1; lh = max(1, lh >> 1)
        raw = np.frombuffer(b, np.uint8, sz0, l0)
        idx = np.concatenate([raw & 15, raw >> 4]) if bpp == 4 else raw
        hist = np.bincount(idx, minlength=256).astype(np.float64)
        wgt = hist * (pal[:, 3] >= 128)
        if wgt.sum() == 0: wgt = hist
        out.append((pal[:, :3] * wgt[:, None]).sum(0) / max(1.0, wgt.sum()))
        p = q; p += -p % 16
    return np.array(out) if out else np.zeros((0, 3))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('out')
    ap.add_argument('--col', type=float, default=25.); ap.add_argument('--ground', type=float, default=50.)
    ap.add_argument('--block', type=float, default=100.); ap.add_argument('--minh', type=float, default=4.)
    ap.add_argument('--mesh', type=float, default=0., help='>0: настоящие упрощённые меши: размер сетки склейки вершин, м (например 5), один тёмный тон')
    ap.add_argument('--muted', type=float, default=0., help='в режиме --mesh цвет вершин из текстуры кусков, приглушённый: доля серого 0..1 (0 — один тон --tone)')
    ap.add_argument('--noground', action='store_true', help='в режиме --mesh без квадратов земли (земля — подстилка движка)')
    ap.add_argument('--tone', default='72,80,84', help='основной тон мешей R,G,B')
    a = ap.parse_args()
    b = Path(a.level).read_bytes()
    tm = tex_means(b)
    d = shr7read.load(a.level, far=False, owner=0)
    P = d['P']; TEX = d['TEX']; FL = d['FL']; OFF = d['OFF']; VS = d['VS']
    keep = (FL & (1 | 2 | 4)) == 0   # без полупрозрачных и неба
    P = P[keep]; TEX = TEX[keep]; OFF = OFF[keep]; VS = VS[keep]
    n = len(P); print('треугольников', n)
    # вершинный цвет: по 3 вершинам байты +4..+8 (ABGR, R первым)
    buf = np.frombuffer(b, np.uint8)
    vc = np.zeros((n, 3))
    for k in range(3):
        o = OFF + k * VS
        vc += buf[o[:, None] + np.arange(4, 7)[None, :]]
    vc /= 3.0
    col = np.where((TEX >= 0)[:, None] & (TEX < len(tm))[:, None], tm[np.clip(TEX, 0, max(0, len(tm) - 1))], 255.0) * (vc / 255.0)
    cen = P.mean(1); ymax = P[:, :, 1].max(1); ymin = P[:, :, 1].min(1)
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]
    nrm = np.cross(e1, e2); area = np.linalg.norm(nrm, axis=1) * .5 + 1e-6
    axz = np.abs(nrm[:, 1]) * .5   # площадь проекции на землю
    C = a.col; G = a.ground
    x0 = float(cen[:, 0].min()); z0 = float(cen[:, 2].min())
    ci = np.floor((cen[:, 0] - x0) / C).astype(np.int64); cj = np.floor((cen[:, 2] - z0) / C).astype(np.int64)
    nj = int(cj.max()) + 1; key = ci * nj + cj
    order = np.argsort(key, kind='stable'); ks = key[order]; ub, st = np.unique(ks, return_index=True); en = np.append(st[1:], len(ks))
    cols = {}
    for u, s, e in zip(ub, st, en):
        ix = order[s:e]
        base = float(np.percentile(ymin[ix], 10))
        big = ix[axz[ix] > .3]
        top = float(ymax[big].max()) if len(big) else float(ymax[ix].max())
        top = min(top, float(np.percentile(ymax[ix], 99.5)) + 3.0)
        roof = ix[ymax[ix] >= top - 2.5]; wall = ix[(ymax[ix] > base + 3.0)]
        w1 = area[roof]; ctop = (col[roof] * w1[:, None]).sum(0) / w1.sum()
        if len(wall): w2 = area[wall]; cw = (col[wall] * w2[:, None]).sum(0) / w2.sum()
        else: cw = ctop
        gr = ix[ymax[ix] < base + 1.0]
        if len(gr): w3 = area[gr]; cg = (col[gr] * w3[:, None]).sum(0) / w3.sum()
        else: cg = ctop
        cols[(int(u // nj), int(u % nj))] = (base, top, ctop, cw, cg)
    if a.mesh > 0:
        # настоящие упрощённые меши (не ящики): оставляем только то, что выше земли колонки (крыши и стены, >= minh), вершины склеиваем сеткой a.mesh м (кластеризация вершин —
        # fast-simplification у этого города упирается в разрывы поверхности на ~15 % и не сходится); земля — квадраты G м, один тёмный тон, тень по нормали
        tone = np.array([float(x) for x in a.tone.split(',')]); sun = np.array([.35, .8, .3]); sun /= np.linalg.norm(sun)
        bmap = {k: v[0] for k, v in cols.items()}
        base_t = np.array([bmap.get((int(i), int(j)), 0.0) for i, j in zip(ci, cj)])
        sel = (ymax - base_t) >= a.minh
        Bk = a.block; bi = np.floor(cen[:, 0] / Bk).astype(np.int64); bj = np.floor(cen[:, 2] / Bk).astype(np.int64)
        V = bytearray(); I = bytearray(); tab = []
        gnd = {}
        for (i, j), (base, top, ctop, cw, cg) in cols.items():
            gx = int(((i + .5) * C) // G); gz = int(((j + .5) * C) // G); gnd.setdefault((gx, gz), []).append(base)
        gkey = {}
        for (gx, gz), v in gnd.items():
            cx_ = x0 + (gx + .5) * G; cz_ = z0 + (gz + .5) * G; gkey.setdefault((int(np.floor(cx_ / Bk)), int(np.floor(cz_ / Bk))), []).append((cx_, cz_, float(np.median(v))))
        if a.noground: gkey = {}
        allk = set(zip(bi[sel].tolist(), bj[sel].tolist())) | set(gkey.keys())
        for (kx, kz) in sorted(allk):
            cx = (kx + .5) * Bk; cz = (kz + .5) * Bk; verts = []; idx = []
            ix = np.nonzero(sel & (bi == kx) & (bj == kz))[0]
            if len(ix):
                T = P[ix].reshape(-1, 3)
                q = np.floor(T / a.mesh).astype(np.int64); uq, inv = np.unique(q, axis=0, return_inverse=True)
                sums = np.zeros((len(uq), 3)); np.add.at(sums, inv, T); pts = sums / np.bincount(inv, minlength=len(uq))[:, None]
                cnt_ = np.bincount(inv, minlength=len(uq))[:, None]; csum = np.zeros((len(uq), 3)); np.add.at(csum, inv, np.repeat(col[ix], 3, axis=0)); vcol = csum / cnt_
                f = inv.reshape(-1, 3); ok = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2]); f = f[ok]
                if len(f):
                    f = np.unique(np.sort(f, axis=1), axis=0)
                    fn = np.cross(pts[f[:, 1]] - pts[f[:, 0]], pts[f[:, 2]] - pts[f[:, 0]]); vn = np.zeros_like(pts)
                    for c in range(3): np.add.at(vn, f[:, c], np.abs(fn))   # без знака: порядок вершин после склейки не хранит сторону
                    ln = np.linalg.norm(vn, axis=1, keepdims=True); ln[ln == 0] = 1; vn /= ln
                    lam = 0.5 + 0.5 * np.clip(vn @ sun, 0, 1)
                    h0 = float(pts[:, 1].min()); h1 = float(pts[:, 1].max()); hs = 0.78 + 0.22 * np.clip((pts[:, 1] - h0) / max(1.0, h1 - h0), 0, 1)
                    if a.muted > 0:
                        lum = (vcol * np.array([.3, .59, .11])).sum(1, keepdims=True); base_c = (vcol * (1 - a.muted) + lum * a.muted) * 0.8
                    else: base_c = np.broadcast_to(tone[None, :], vcol.shape)
                    for (x, y, z), cc in zip(pts, np.clip(base_c * (lam * hs)[:, None], 0, 255).astype(int)):
                        verts.append((0xff000000 | (cc[2] << 16) | (cc[1] << 8) | cc[0], x - cx, y, z - cz))
                    idx += [int(t) for t in f.reshape(-1)]
            for (gx_, gz_, gy) in gkey.get((kx, kz), []):
                s0 = len(verts); cc = np.clip(tone * 0.7, 0, 255).astype(int); c = 0xff000000 | (cc[2] << 16) | (cc[1] << 8) | cc[0]
                for (x, z) in ((gx_ - G / 2, gz_ - G / 2), (gx_ + G / 2, gz_ - G / 2), (gx_ + G / 2, gz_ + G / 2), (gx_ - G / 2, gz_ + G / 2)): verts.append((c, x - cx, gy - .3, z - cz))
                idx += [s0, s0 + 2, s0 + 1, s0, s0 + 3, s0 + 2]
            if not verts: continue
            v0 = len(V) // 16; i0 = len(I) // 2
            for (c, x, y, z) in verts: V += struct.pack('<Ifff', c, x, y, z)
            for t in idx: I += struct.pack('<H', t)
            ys = [v[2] for v in verts]; tab.append((cx, cz, min(ys), max(ys), Bk / 2, v0, len(verts), i0, len(idx)))
        nb = len(tab); hdr = struct.pack('<4sIfI', b'SIL1', nb, Bk, 0) + b'\0' * 16
        voff = 32 + 48 * nb; ioff = voff + len(V); out = bytearray(hdr)
        for (cx, cz, y0, y1, half, v0, nv, i0, ni) in tab: out += struct.pack('<6f6I', cx, cz, y0, y1, half, 0.0, voff + v0 * 16, nv, ioff + i0 * 2, ni, 0, 0)
        out += V; out += I; Path(a.out).write_bytes(bytes(out))
        print('mesh: блоков', nb, 'байт', len(out), 'вершин', len(V) // 16, 'треугольников', len(I) // 6); return
    # земля: квадраты G
    gcell = {}
    for (i, j), (base, top, ctop, cw, cg) in cols.items():
        gx = int((x0 + (i + .5) * C - x0) // G); gz = int((z0 + (j + .5) * C - z0) // G)
        gcell.setdefault((gx, gz), []).append((base, cg))
    # ящики: склейка вдоль X
    boxes = []
    for j in sorted(set(j for (_, j) in cols)):
        row = sorted(i for (i, jj) in cols if jj == j)
        k = 0
        while k < len(row):
            i = row[k]; base, top, ctop, cw, cg = cols[(i, j)]
            if top - base < a.minh: k += 1; continue
            run = [i]; tops = [top]; bases = [base]; cts = [ctop]; cws = [cw]; m = k + 1
            while m < len(row) and row[m] == run[-1] + 1:
                bb, tt, ct, cwk, _ = cols[(row[m], j)]
                if tt - bb < a.minh or abs(tt - tops[-1]) > 2.5: break
                run.append(row[m]); tops.append(tt); bases.append(bb); cts.append(ct); cws.append(cwk); m += 1
            xa = x0 + run[0] * C; xb = x0 + (run[-1] + 1) * C; za = z0 + j * C; zb = za + C
            boxes.append((xa, xb, za, zb, min(bases), max(tops), np.mean(cts, 0), np.mean(cws, 0)))
            k = m
    print('колонок', len(cols), 'ящиков', len(boxes), 'земли', len(gcell))
    Bk = a.block
    blocks = {}
    def bkey(x, z): return (int(np.floor(x / Bk)), int(np.floor(z / Bk)))
    for bx in boxes: blocks.setdefault(bkey((bx[0] + bx[1]) / 2, (bx[2] + bx[3]) / 2), {'box': [], 'gr': []})['box'].append(bx)
    for (gx, gz), v in gcell.items():
        cx = x0 + (gx + .5) * G; cz = z0 + (gz + .5) * G
        base = float(np.median([t[0] for t in v])); cg = np.mean([t[1] for t in v], 0)
        blocks.setdefault(bkey(cx, cz), {'box': [], 'gr': []})['gr'].append((cx - G / 2, cx + G / 2, cz - G / 2, cz + G / 2, base, cg))
    def abgr(c, f=1.0):
        c = np.clip(np.asarray(c) * f, 0, 255).astype(int); return 0xff000000 | (c[2] << 16) | (c[1] << 8) | c[0]
    V = bytearray(); I = bytearray(); tab = []
    nv_all = 0
    for (bi, bj), blk in sorted(blocks.items()):
        cx = (bi + .5) * Bk; cz = (bj + .5) * Bk; v0 = len(V) // 16; i0 = len(I) // 2; ys = []
        verts = []; idx = []
        for (xa, xb, za, zb, base, cg) in blk['gr']:
            s = len(verts); c = abgr(cg, .85)
            for (x, z) in ((xa, za), (xb, za), (xb, zb), (xa, zb)): verts.append((c, x - cx, base, z - cz)); ys.append(base)
            idx += [s, s + 2, s + 1, s, s + 3, s + 2]
        for (xa, xb, za, zb, y0, y1, ct, cw) in blk['box']:
            s = len(verts); ctp = abgr(ct, 1.0); cbt = abgr(cw, .55)
            for (x, z, yy, c) in ((xa, za, y1, ctp), (xb, za, y1, ctp), (xb, zb, y1, ctp), (xa, zb, y1, ctp),
                                  (xa, za, y0, cbt), (xb, za, y0, cbt), (xb, zb, y0, cbt), (xa, zb, y0, cbt)):
                verts.append((c, x - cx, yy, z - cz))
            ys += [y0, y1]
            idx += [s, s + 2, s + 1, s, s + 3, s + 2,           # верх
                    s, s + 1, s + 5, s, s + 5, s + 4,           # -Z
                    s + 1, s + 2, s + 6, s + 1, s + 6, s + 5,   # +X
                    s + 2, s + 3, s + 7, s + 2, s + 7, s + 6,   # +Z
                    s + 3, s, s + 4, s + 3, s + 4, s + 7]       # -X
        for (c, x, y, z) in verts: V += struct.pack('<Ifff', c, x, y, z)
        for t in idx: I += struct.pack('<H', t)
        tab.append((cx, cz, min(ys), max(ys), Bk / 2, v0, len(verts), i0, len(idx)))
    nb = len(tab); hdr = struct.pack('<4sIfI', b'SIL1', nb, Bk, 0) + b'\0' * 16
    tsz = 48 * nb; voff = 32 + tsz; ioff = voff + len(V)
    out = bytearray(hdr)
    for (cx, cz, y0, y1, half, v0, nv, i0, ni) in tab:
        out += struct.pack('<6f6I', cx, cz, y0, y1, half, 0.0, voff + v0 * 16, nv, ioff + i0 * 2, ni, 0, 0)
    out += V; out += I
    Path(a.out).write_bytes(bytes(out))
    print('блоков', nb, 'байт', len(out), 'вершин', len(V) // 16, 'индексов', len(I) // 2)


main()
