#!/usr/bin/env python3
"""Офлайн-экспорт HLOD: дальние кварталы блоками 160 м, упрощение meshoptimizer (MIT) с запиранием вершин на краях блоков,
цвет в вершинах вместо текстур (средний цвет текстуры треугольника).
   python tools/hlod_export.py level.shr --out hlod.shr [--block 160 --tris 125 --err 6 --stats]
Формат HLD1 (все числа little-endian):
  заголовок 32 Б: 'HLD1', nblocks u32, block f32, nbytes u32 (всего), 16 нулей
  таблица блоков по 48 Б: cx, cz, y0 f32 (центр блока и высота-опора), nv u32, ni u32, voff u32, ioff u32 (от начала файла),
                          rad f32 (радиус по ящику, для дальности), 8 нулей
  вершина 12 Б: color u32 ABGR, x s16, y s16, z s16 (шаг 1/8 м от (cx, y0, cz)), 2 Б выравнивания; индексы u16."""
import sys, argparse, struct
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read
import meshoptimizer as mo

import ctypes
_lib = mo.simplifier.lib if hasattr(mo.simplifier, 'lib') else None
if _lib is not None:   # обёртка не задаёт argtypes: float не конвертируется
    _P = ctypes.POINTER
    _lib.meshopt_simplifyWithAttributes.argtypes = [_P(ctypes.c_uint), _P(ctypes.c_uint), ctypes.c_size_t, _P(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t,
        _P(ctypes.c_float), ctypes.c_size_t, _P(ctypes.c_float), ctypes.c_size_t, _P(ctypes.c_ubyte), ctypes.c_size_t, ctypes.c_float, ctypes.c_uint, _P(ctypes.c_float)]
    _lib.meshopt_simplifyWithAttributes.restype = ctypes.c_size_t
_lib.meshopt_simplifySloppy.argtypes = [_P(ctypes.c_uint), _P(ctypes.c_uint), ctypes.c_size_t, _P(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_float, _P(ctypes.c_float)]
_lib.meshopt_simplifySloppy.restype = ctypes.c_size_t
STEP = 8.0   # квантование вершин: 1/8 м


def tex_avg_colors(path):
    """средний цвет каждой текстуры уровня (RGB 0..255) по индексам уровня 0 и палитре; порядок индексов не важен"""
    b = Path(path).read_bytes()
    ntex = struct.unpack_from('<I', b, 4)[0]
    hw, hh = struct.unpack_from('<ii', b, 12 + 14 * 4)
    p = 104 + hw * hh * 4 * 2; p = (p + 15) & ~15; p += hw * hh * 2 * 2; p = (p + 15) & ~15
    out = np.full((ntex, 3), 128.0)
    for i in range(ntex):
        w, h, lev = struct.unpack_from('<HHH', b, p)
        t4 = b[p + 6] == 4; pre = b[p + 7] == 1
        pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4).astype(np.float64); p += 16 + 1024
        lw, lh = w, h; first = None
        for l in range(lev):
            rb = (16 if (lw + 1) >> 1 < 16 else (lw + 1) >> 1) if t4 else (16 if (pre and lw < 16) else lw)
            rows = (lh + 7) & ~7 if pre else lh
            n = rb * rows
            if l == 0: first = (p, rb, rows, lw, lh)
            p += n; p = (p + 15) & ~15; lw >>= 1; lh = lh > 1 and lh >> 1 or 1
        q, rb, rows, lw0, lh0 = first
        # ширина строки: texRowBytes (viewer): t4 -> w/2, иначе w; для узких мипов 16 Б. Берём байты уровня 0 целиком
        raw = np.frombuffer(b, np.uint8, rb * rows, q)
        if t4: idx = np.concatenate([raw & 15, raw >> 4])
        else: idx = raw
        hist = np.bincount(idx, minlength=256).astype(np.float64)
        wgt = hist * (pal[:, 3] / 255.0)
        if wgt.sum() > 0: out[i] = (pal[:, :3] * wgt[:, None]).sum(0) / wgt.sum()
    tab = struct.unpack_from('<I', b, 76)[0]
    assert p == tab, 'таблица текстур разошлась: %d != %d' % (p, tab)
    return out


def boxes_block(pos, col, cell, ox, oz):
    """блок как столбики: сетка ячеек cell м, в ячейке со стенами (дом) коробка от низа до верха стен, крыша и стены разного цвета.
    pos (N*3,3) вершины треугольников, col (N,3) цвет на треугольник. -> (verts [(x,y,z,rgb)], idx)"""
    P = pos.reshape(-1, 3, 3).astype(np.float64); n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); ar = np.linalg.norm(n, axis=1) + 1e-12; ny = np.abs(n[:, 1]) / ar
    c = P.mean(1); half = ar * 0.5
    ci = np.floor((c[:, 0] - ox) / cell).astype(int); cj = np.floor((c[:, 2] - oz) / cell).astype(int)
    cells = {}
    wall = ny < 0.35
    for i in np.where(wall & (half > 0.3))[0]:
        cells.setdefault((ci[i], cj[i]), []).append(i)
    H = {}
    for (a, b), L in cells.items():
        L = np.array(L); area = half[L].sum()
        ymin = P[L][:, :, 1].min(); ymax = P[L][:, :, 1].max()
        if area < 25 or ymax - ymin < 4.: continue
        # крыша: горизонтальные треугольники ячейки не ниже середины стен
        rm = (ci == a) & (cj == b) & ~wall & (c[:, 1] > ymin + 0.5 * (ymax - ymin))
        top = max(ymax, P[rm][:, :, 1].max() if rm.any() else ymax)
        wc = (col[L] * half[L, None]).sum(0) / half[L].sum()
        rc = (col[rm] * half[rm, None]).sum(0) / half[rm].sum() if rm.any() else wc
        H[(a, b)] = (max(ymin, top - 45.), top, wc, rc)   # высота коробки не больше 45 м: скальные стены и сваи уходят вниз на сотни метров и торчали серой плитой
    verts = []; idx = []
    def quad(q, rgb):
        base = len(verts)
        for v in q: verts.append((v[0], v[1], v[2], rgb))
        idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    for (a, b), (y0, y1, wc, rc) in H.items():
        x0 = ox + a * cell; x1 = x0 + cell; z0 = oz + b * cell; z1 = z0 + cell
        quad([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], np.clip(rc, 0, 255))   # крыша, смотрит вверх
        for (nb, q, k) in (((a - 1, b), [(x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0)], 0.80),
                           ((a + 1, b), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], 0.80),
                           ((a, b - 1), [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], 0.65),
                           ((a, b + 1), [(x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1)], 0.65)):
            if nb in H and H[nb][1] >= y1 - 0.5 and H[nb][0] <= y0 + 0.5: continue   # сосед закрывает стену
            quad(q, np.clip(wc * k, 0, 255))
    return verts, idx


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('--out'); ap.add_argument('--block', type=float, default=160.)
    ap.add_argument('--mode', default='boxes', choices=['boxes', 'sloppy']); ap.add_argument('--cell', type=float, default=16.); ap.add_argument('--tris', type=int, default=125); ap.add_argument('--err', type=float, default=6.); ap.add_argument('--stats', action='store_true')
    a = ap.parse_args()
    d = shr7read.load(a.level, far=False, owner=0)
    keep = (d['FL'] & (1 | 2 | 4)) == 0
    P = d['P'][keep]; T = d['TEX'][keep]
    tc = tex_avg_colors(a.level)
    col = np.clip(tc[np.clip(T, 0, len(tc) - 1)], 0, 255)            # (N,3) на треугольник
    print('треугольников %d, текстур %d, средний цвет по уровню %s' % (len(P), len(tc), col.mean(0).round()))
    c = P.mean(1)
    B = np.floor(c[:, [0, 2]] / a.block).astype(np.int64)
    key = (B[:, 0] - B[:, 0].min()) * 100000 + (B[:, 1] - B[:, 1].min())
    # общие позиции вершин между блоками: вершина запирается, если она есть у треугольников двух блоков
    q = np.round(P.reshape(-1, 3) * 16).astype(np.int64)   # шаг 1/16 м
    h = (q[:, 0] * 73856093) ^ (q[:, 1] * 19349663) ^ (q[:, 2] * 83492791)
    vb = np.repeat(key, 3)
    order = np.argsort(h, kind='stable'); hs = h[order]; bs = vb[order]
    # на каждый хэш: число различных блоков
    newg = np.r_[True, hs[1:] != hs[:-1]]; gid = np.cumsum(newg) - 1
    first = np.full(gid[-1] + 1, -1, np.int64); bmin = np.full(gid[-1] + 1, np.iinfo(np.int64).max); bmax = np.full(gid[-1] + 1, -1)
    np.minimum.at(bmin, gid, bs); np.maximum.at(bmax, gid, bs)
    shared = (bmin != bmax)[gid]
    lock_all = np.zeros(len(h), bool); lock_all[order] = shared
    blocks = []; tot_in = tot_out = 0; nvt = 0
    for k in np.unique(key):
        sel = np.where(key == k)[0]
        n = len(sel)
        pos = P[sel].reshape(-1, 3).astype(np.float32)
        colv = np.repeat(col[sel], 3, axis=0).astype(np.float32) / 255.0
        lk = lock_all.reshape(-1, 3)[sel].reshape(-1)
        if a.mode == 'boxes':
            bv, bi = boxes_block(pos, np.repeat(col[sel], 3, axis=0)[::3], a.cell, float(np.floor(c[sel, 0].min() / a.cell) * a.cell), float(np.floor(c[sel, 2].min() / a.cell) * a.cell))
            if not bi: continue
            pos = np.array([v[:3] for v in bv], np.float32); colv = np.array([v[3] for v in bv], np.float32) / 255.0
            out = np.array(bi, np.uint32); nout = len(out); idx = None
            used = np.arange(len(pos))
            rm = np.arange(len(pos))
            ox = np.floor((pos[:, 0].min() + pos[:, 0].max()) / 2); oz = np.floor((pos[:, 2].min() + pos[:, 2].max()) / 2); y0 = float(pos[:, 1].min())
            pv = pos; cv = colv
            qp = np.round((pv - np.array([ox, y0, oz], np.float32)) * STEP)
            if np.abs(qp).max() > 32767: print('блок %s вне диапазона s16' % k); continue
            rgba = (np.clip(cv * 255 + 0.5, 0, 255).astype(np.uint32))
            abgr = (np.uint32(0xff) << 24) | (rgba[:, 2] << 16) | (rgba[:, 1] << 8) | rgba[:, 0]
            rad = float(np.hypot(pos[:, 0].max() - pos[:, 0].min(), pos[:, 2].max() - pos[:, 2].min()) / 2)
            blocks.append((float(ox), float(oz), y0, abgr, qp.astype(np.int16), rm[out].astype(np.uint16), rad, n))
            tot_in += n; tot_out += nout // 3; nvt += len(used)
            continue
        idx = np.arange(len(pos), dtype=np.uint32)
        tgt = min(len(idx), max(3, 3 * a.tris))
        dst = np.zeros(len(idx), np.uint32)
        # суп из отдельных домов не сворачивается обычным упрощением (топология: 27 тыс. -> 4 тыс.), поэтому кластеризация по сетке (meshopt sloppy):
        # края блоков не запираются, щели между блоками на 200-600 м субпиксельные и тонут в дымке
        PP = ctypes.POINTER
        nout = _lib.meshopt_simplifySloppy(dst.ctypes.data_as(PP(ctypes.c_uint)), idx.ctypes.data_as(PP(ctypes.c_uint)), len(idx),
                                           np.ascontiguousarray(pos).ctypes.data_as(PP(ctypes.c_float)), len(pos), 12, tgt, float(a.err), None)
        out = dst[:nout]
        used = np.unique(out)
        rm = np.full(len(pos), -1, np.int64); rm[used] = np.arange(len(used))
        ox = np.floor(sel.size and ((pos[:, 0].min() + pos[:, 0].max()) / 2)); oz = np.floor((pos[:, 2].min() + pos[:, 2].max()) / 2)
        y0 = float(pos[:, 1].min())
        pv = pos[used]; cv = colv[used]
        qp = np.round((pv - np.array([ox, y0, oz], np.float32)) * STEP)
        if np.abs(qp).max() > 32767: print('блок %s вне диапазона s16' % k); continue
        rgba = (np.clip(cv * 255 + 0.5, 0, 255).astype(np.uint32))
        abgr = (np.uint32(0xff) << 24) | (rgba[:, 2] << 16) | (rgba[:, 1] << 8) | rgba[:, 0]
        rad = float(np.hypot(pos[:, 0].max() - pos[:, 0].min(), pos[:, 2].max() - pos[:, 2].min()) / 2)
        blocks.append((float(ox), float(oz), y0, abgr, qp.astype(np.int16), rm[out].astype(np.uint16), rad, n))
        tot_in += n; tot_out += nout // 3; nvt += len(used)
    print('блоков %d, треугольников %d -> %d (%.1f%%), вершин %d, запертых вершин %.0f%%' % (len(blocks), tot_in, tot_out, 100. * tot_out / max(tot_in, 1), nvt, 100. * lock_all.mean()))
    if a.stats or not a.out:
        for i, bl in enumerate(blocks[:12]): print('  блок', i, 'центр %.0f,%.0f' % (bl[0], bl[1]), 'исходных %d -> %d тр, вершин %d' % (bl[7], len(bl[5]) // 3, len(bl[3])))
    if a.out:
        nb = len(blocks); toff = 32 + 48 * nb; blob = bytearray(); ents = []
        for (ox, oz, y0, abgr, qp, ix, rad, n) in blocks:
            voff = toff + len(blob)
            vb_ = np.zeros((len(abgr), 6), np.uint16)
            vb_[:, 0] = (abgr & 0xffff).astype(np.uint16); vb_[:, 1] = (abgr >> 16).astype(np.uint16)
            vb_[:, 2:5] = qp.view(np.uint16)
            blob += vb_.tobytes()
            ioff = toff + len(blob); blob += ix.tobytes()
            if len(blob) % 4: blob += b'\0\0'
            ents.append(struct.pack('<3fIIIIf16x', ox, oz, y0, len(abgr), len(ix), voff, ioff, rad))
        hdr = struct.pack('<4sIfI16x', b'HLD1', nb, a.block, toff + len(blob))
        Path(a.out).write_bytes(hdr + b''.join(ents) + bytes(blob))
        print('записано', a.out, toff + len(blob), 'байт')


if __name__ == '__main__':
    main()
