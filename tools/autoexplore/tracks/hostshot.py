#!/usr/bin/env python3
"""Снимок вида хост-рендером (полоса «Трассы» автоисследователя): что видит камера игры в точке находки.
Рисует город уровня из level.shr (owner 0: куски, текстуры, цвет вершин, альфа-тест, смешивание), без неба/пропов/машин/персонажей.
Режимы: normal — фон цвета неба; holes — фон пурпурный (как служебный clearchk игры): всё, что не закрыто геометрией, остаётся пурпурным (дыра в мире),
число пурпурных пикселей попадает в подпись. Метка находки — красный крест и кольцо в проекции точки.
  python3 hostshot.py LEVEL.shr X Y Z [HEADING] [-o out.png] [--mode normal|holes] [--label текст] [--top]
API: S = Shooter(path); S.shot(x, y, z, heading, out_png, label='', mode='normal', top=False) -> dict(holes=%, tris=n, ms=)"""
import ctypes, math, os, struct, subprocess, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
def _lib():
    so = HERE / ('librast.dylib' if sys.platform == 'darwin' else 'librast.so'); src = HERE / 'rast.c'
    if not so.exists() or so.stat().st_mtime < src.stat().st_mtime:
        subprocess.check_call(['cc', '-O2', '-shared', '-fPIC', str(src), '-o', str(so), '-lm'])
    return ctypes.CDLL(str(so))
LIB = _lib()
P = ctypes.POINTER
LIB.render.argtypes = [ctypes.c_int, P(ctypes.c_float), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
                       ctypes.c_float, ctypes.c_float, ctypes.c_float, P(ctypes.c_uint8), P(ctypes.c_float), ctypes.c_int, P(ctypes.c_int)]
LIB.render.restype = ctypes.c_int
def ptr(a, t): return a.ctypes.data_as(P(t))
REC = np.dtype([('bb', '<f4', 6), ('tex', '<i4'), ('flags', '<i4'), ('nv', '<i4'), ('ni', '<i4'), ('owner', '<i4'), ('o', '<f4', 3), ('sc', '<f4'), ('off', '<u4'), ('nf', '<u4'), ('cell', '<u4'), ('pad', '<u4', 2)])
CELL = np.dtype([('bb', '<f4', 6), ('first', '<u4'), ('n', '<u4'), ('owner', '<u4'), ('off', '<u4'), ('size', '<u4'), ('pad', '<u4')])
V16 = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('pad', '<i2')])
V12 = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u2'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2')])
F_NOIDX, F_V12 = 16, 32
class Shooter:
    def __init__(self, path, size=(480, 272), fovy_deg=60.0, maxd=250.0):
        self.path = str(path); b = self.b = open(path, 'rb').read(); assert b[:4] == b'SHR7', 'не SHR7'
        self.ntex, self.npc = struct.unpack_from('<II', b, 4); self.spawn = struct.unpack_from('<4f', b, 36)
        ptab, ncell, ctab = struct.unpack_from('<I', b, 76)[0], struct.unpack_from('<I', b, 80)[0], struct.unpack_from('<I', b, 84)[0]
        self.rec = np.frombuffer(b, REC, self.npc, ptab); self.cell = np.frombuffer(b, CELL, ncell, ctab)
        self.W, self.H = size; self.fy = self.H / 2 / math.tan(math.radians(fovy_deg) / 2); self.fx = self.fy; self.maxd = maxd
        r = self.rec; self.cen = (r['bb'][:, :3] + r['bb'][:, 3:]) / 2; self.rad = .5 * np.linalg.norm(r['bb'][:, 3:] - r['bb'][:, :3], axis=1)
        self.city = np.where((r['owner'] == 0) & ((r['flags'] & 4) == 0))[0]
        hd = struct.unpack_from('<11f3f', b, 12); self.hW, self.hH = struct.unpack_from('<II', b, 12 + 14 * 4); self.hox, self.hoz, self.hcell = hd[11], hd[12], hd[13]
        self.hm = np.frombuffer(b, '<i2', self.hW * self.hH * 4, 104).reshape(self.hH, self.hW, 4)
        off = struct.unpack_from('<I', b, 88)[0]; self.pvs = None
        if off and b[off:off + 4] == b'PVS1':
            pox, poz, pcell = struct.unpack_from('<3f', b, off + 4); pW, pH, pool, _ = struct.unpack_from('<4I', b, off + 16)
            self.pvs = (pox, poz, pcell, pW, pH, np.frombuffer(b, '<u4', 2 * pW * pH, off + 32).reshape(-1, 2), np.frombuffer(b, '<u2', pool, off + 32 + 8 * pW * pH))
        self._tex = None
    def pvs_list(self, x, z):
        """Список видимых кусков PVS1 для клетки 20 м под камерой (как у игры); None — нет данных, рисуется всё."""
        if not self.pvs: return None
        ox, oz, cell, W, H, ent, pl = self.pvs; gx, gz = int((x - ox) // cell), int((z - oz) // cell)
        if not (0 <= gx < W and 0 <= gz < H): return None
        s, n = ent[gz * W + gx]
        return None if n == 0xFFFFFFFF else pl[s:s + n]
    def ground(self, x, z, ref=None):
        """Высота опоры под точкой (м): ближайшая к ref из слоёв карты высот клетки; нет данных — None."""
        gx, gz = int((x - self.hox) // self.hcell), int((z - self.hoz) // self.hcell)
        if not (0 <= gx < self.hW and 0 <= gz < self.hH): return None
        h = self.hm[gz, gx]; h = h[h != -32768] * 0.01
        if not len(h): return None
        return float(h[np.argmin(np.abs(h - ref))]) if ref is not None else float(h.max())
    def _textures(self):
        if self._tex is not None: return self._tex
        b = self.b; hw, hh = struct.unpack_from('<ii', b, 68); p = 104 + hw * hh * 8; p = (p + 15) & ~15; p += hw * hh * 4; p = (p + 15) & ~15
        out = []
        for _ in range(self.ntex):
            w, h, lv = struct.unpack_from('<HHH', b, p); t4 = b[p + 6] == 4; pre = b[p + 7] == 1
            pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4); p += 16 + 1024; lw, lh = w, h; levels = []
            for l in range(lv):
                rb = ((lw + 1) >> 1 if (lw + 1) >> 1 >= 16 else 16) if t4 else (lw if not (pre and lw < 16) else 16)
                hh_ = (lh + 7) & ~7 if pre else lh; n = rb * hh_; raw = np.frombuffer(b, np.uint8, n, p); p += n; p = (p + 15) & ~15
                levels.append((lw, lh, rb, raw)); lw >>= 1; lh = lh > 1 and lh >> 1 or 1
            out.append(dict(w=w, h=h, lv=lv, t4=t4, pre=pre, pal=pal, levels=levels))
        self._tex = out; return out
    def _decode(self, t, maxdim=128):
        k = 0
        while k + 1 < t['lv'] and max(t['levels'][k][0], t['levels'][k][1]) > maxdim: k += 1
        lw, lh, rb, raw = t['levels'][k]
        if not t['pre']: a = raw.reshape(-1, rb)[:lh]
        else:
            hh_ = (lh + 7) & ~7; bx = rb // 16 if rb >= 16 else 1
            a = raw[:rb * hh_].reshape(hh_ // 8, bx, 8, 16).transpose(0, 2, 1, 3).reshape(hh_, bx * 16)[:lh, :rb]
        if t['t4']: idx = np.stack([a & 15, a >> 4], -1).reshape(a.shape[0], -1)[:, :lw]
        else: idx = a[:, :lw]
        return t['pal'][idx], lw, lh
    def piece_tris(self, pi):
        """Треугольники одного куска города в мировых координатах: (N,3,3) float32 или None."""
        r = self.rec[pi]; nv = int(r['nv']); ni = int(r['ni']); fgs = int(r['flags']); blob = int(self.cell['off'][int(r['cell'])]) + int(r['off']); v12 = bool(fgs & F_V12); vs = 12 if v12 else 16; dt = V12 if v12 else V16
        if fgs & F_NOIDX:
            n = ni - ni % 3
            if n < 3: return None, None
            vi = np.frombuffer(self.b, dt, n, blob)
        else:
            verts = np.frombuffer(self.b, dt, nv, blob); io = blob + ((nv * vs + 15) & ~15); idx = np.frombuffer(self.b, '<u2', ni - ni % 3, io)
            if len(idx) == 0 or idx.max() >= nv: return None, None
            vi = verts[idx]
        wp = np.stack([vi['x'], vi['y'], vi['z']], 1).astype(np.float32) * (float(r['sc']) / 32768.0) + r['o']
        return wp.reshape(-1, 3, 3), None
    def region_tris(self, x0, x1, z0, z1, owners=(0,)):
        """Все треугольники города (owner 0, без неба), чей bbox пересекает прямоугольник [x0,x1]x[z0,z1]: (N,3,3) в мировых координатах и (N,) номера кусков."""
        r = self.rec; bb = r['bb']; sel = np.where(np.isin(r['owner'], owners) & ((r['flags'] & 4) == 0) & (bb[:, 0] <= x1) & (bb[:, 3] >= x0) & (bb[:, 2] <= z1) & (bb[:, 5] >= z0))[0]
        out = []; ids = []
        for pi in sel:
            rr = r[pi]; nv = int(rr['nv']); ni = int(rr['ni']); fgs = int(rr['flags']); blob = int(self.cell['off'][int(rr['cell'])]) + int(rr['off']); v12 = bool(fgs & F_V12); vs = 12 if v12 else 16; dt = V12 if v12 else V16
            if fgs & F_NOIDX:
                n = ni - ni % 3
                if n < 3: continue
                vi = np.frombuffer(self.b, dt, n, blob)
            else:
                verts = np.frombuffer(self.b, dt, nv, blob); io = blob + ((nv * vs + 15) & ~15); idx = np.frombuffer(self.b, '<u2', ni - ni % 3, io)
                if len(idx) == 0 or idx.max() >= nv: continue
                vi = verts[idx]
            wp = np.stack([vi['x'], vi['y'], vi['z']], 1).astype(np.float32) * (float(rr['sc']) / 32768.0) + rr['o']
            out.append(wp.reshape(-1, 3, 3)); ids += [int(pi)] * (len(vi) // 3)
        return (np.concatenate(out) if out else np.zeros((0, 3, 3), np.float32)), np.array(ids, np.int64)
    def shot(self, x, y, z, heading=0.0, out=None, label='', mode='normal', top=False, mark=True, use_pvs=True, restrict=None, ret_img=False, vis_out=None, pose=None):
        t0 = time.time(); W, H = self.W, self.H
        tgt = np.array([x, y + 1.4, z]); fw = np.array([math.sin(heading), 0, math.cos(heading)])
        eye = tgt + np.array([0, 60.0, 0]) - fw * 1.0 if top else tgt - fw * 7.5 + np.array([0, 3.2, 0])
        if pose is not None:   # (глаз, курс, наклон): камера задана прямо, цель — впереди на 7,5 м
            eye = np.array(pose[0], float); yw, pt = pose[1], pose[2]; fwd3 = np.array([math.sin(yw) * math.cos(pt), math.sin(pt), math.cos(yw) * math.cos(pt)]); tgt = eye + fwd3 * 7.5
        f = tgt - eye; f /= np.linalg.norm(f); up = np.array([0, 1.0, 0]); s = np.cross(f, up)
        if np.linalg.norm(s) < 1e-6: s = np.array([1.0, 0, 0])   # вид строго вниз: правая сторона — ось x
        s /= np.linalg.norm(s); u = np.cross(s, f)
        dv = self.cen[self.city] - eye; dist = np.linalg.norm(dv, axis=1); fwd = dv @ f; side = np.sqrt(np.maximum(0, dist ** 2 - fwd ** 2)); rad = self.rad[self.city]
        keep = self.city[(dist - rad <= self.maxd) & ~(side * .60 - fwd * .80 > rad)] if not top else self.city[(dist - rad <= 140)]
        if use_pvs and not top:
            pl = self.pvs_list(eye[0], eye[2])
            if pl is not None: keep = np.intersect1d(keep, pl.astype(np.int64))
        if restrict is not None: keep = np.intersect1d(keep, restrict)
        tex = self._textures(); amap = {}; atlas = []; toff = []; tw = []; th = []; off = 0
        pos = []; fl = []; ti = []; dists = []; pcs = []
        for pi in keep:
            r = self.rec[pi]; nv = int(r['nv']); ni = int(r['ni']); fgs = int(r['flags']); ci = int(r['cell']); blob = int(self.cell['off'][ci]) + int(r['off'])
            v12 = bool(fgs & F_V12); vs = 12 if v12 else 16; dt = V12 if v12 else V16
            if fgs & F_NOIDX:
                n = ni - ni % 3; verts = np.frombuffer(self.b, dt, n, blob)
                if n < 3: continue
                vi = verts; idx = None
            else:
                verts = np.frombuffer(self.b, dt, nv, blob); io = blob + ((nv * vs + 15) & ~15)
                idx = np.frombuffer(self.b, '<u2', ni - ni % 3, io)
                if len(idx) == 0 or (idx.max() >= nv): continue
                vi = verts[idx]
            wp = np.stack([vi['x'], vi['y'], vi['z']], 1).astype(np.float32) * (float(r['sc']) / 32768.0) + r['o']
            rel = wp - eye; cam = np.stack([rel @ s, rel @ u, rel @ f], 1).astype(np.float32)
            uv = np.stack([vi['u'], vi['v']], 1).astype(np.float32) / 256.0
            if v12: col = np.ones((len(vi), 4), np.float32)
            else:
                c = vi['c'].astype(np.uint32); col = np.stack([c & 255, (c >> 8) & 255, (c >> 16) & 255, (c >> 24) & 255], 1).astype(np.float32) / 255.0
            tid = int(r['tex'])
            if tid >= 0 and tid < len(tex):
                if tid not in amap:
                    img, lw, lh = self._decode(tex[tid]); amap[tid] = len(toff); toff.append(off); tw.append(lw); th.append(lh); atlas.append(np.ascontiguousarray(img).reshape(-1)); off += lw * lh * 4
                ai = amap[tid]
            else: ai = -1
            nt = len(vi) // 3
            pos.append(np.concatenate([cam, uv, col], 1).reshape(nt, 27)); fl += [fgs & 3] * nt; ti += [ai] * nt; dists += [float(np.linalg.norm(self.cen[pi] - eye))] * nt; pcs += [int(pi)] * nt
        rgb = np.zeros((H, W, 3), np.uint8); bgc = (255, 0, 255) if mode == 'holes' else (176, 196, 222); rgb[:] = bgc
        zb = np.zeros((H, W), np.float32); idb = np.full((H, W), -1, np.int32); drawn = 0; nt_all = 0; stats = {}
        if pos:
            vv = np.ascontiguousarray(np.concatenate(pos, 0), np.float32); fla = np.array(fl, np.int32); tia = np.array(ti, np.int32); nt_all = len(vv)
            order = np.argsort(-np.array(dists)); vv2 = np.ascontiguousarray(vv[order]); fla2 = np.ascontiguousarray(fla[order]); tia2 = np.ascontiguousarray(tia[order])
            atl = np.ascontiguousarray(np.concatenate(atlas) if atlas else np.zeros(4, np.uint8), np.uint8); toff_a = np.array(toff or [0], np.int32); tw_a = np.array(tw or [1], np.int32); th_a = np.array(th or [1], np.int32)
            for ps in (0, 1):
                drawn += LIB.render(len(vv2), ptr(vv2, ctypes.c_float), ptr(tia2, ctypes.c_int), ptr(fla2, ctypes.c_int), ptr(toff_a, ctypes.c_int), ptr(tw_a, ctypes.c_int), ptr(th_a, ctypes.c_int), ptr(atl, ctypes.c_uint8),
                                    W, H, self.fx, self.fy, 0.3, ptr(rgb, ctypes.c_uint8), ptr(zb, ctypes.c_float), ps, ptr(idb, ctypes.c_int))
        if pos:
            ids = np.unique(idb[idb >= 0]); pca = np.array(pcs, np.int64)[order]; vis_pc = np.unique(pca[ids]) if len(ids) else np.array([], np.int64)
            tri_per_pc = np.bincount(np.array(pcs, np.int64), minlength=self.npc); cl = self.rec['cell']
            used_cells = np.unique(cl[np.unique(np.array(pcs, np.int64))]); vis_cells = np.unique(cl[vis_pc]) if len(vis_pc) else np.array([], np.int64)
            waste_cells = np.setdiff1d(used_cells, vis_cells); cell_tris = {int(c): int(tri_per_pc[(cl == c) & (self.rec['owner'] == 0)].sum()) for c in used_cells}
            d_all = np.array(dists)
            stats = dict(sub_tris=nt_all, vis_tris=int(len(ids)), pieces=int(len(np.unique(pcs))), vis_pieces=int(len(vis_pc)), cells=int(len(used_cells)), vis_cells=int(len(vis_cells)),
                         wasted_cell_tris=int(sum(cell_tris[int(c)] for c in waste_cells)), vis_piece_tris=int(tri_per_pc[vis_pc].sum()), vis_cell_tris=int(sum(cell_tris[int(c)] for c in vis_cells)), tris_0_50=int((d_all < 50).sum()), tris_50_115=int(((d_all >= 50) & (d_all < 115)).sum()), tris_115_250=int((d_all >= 115).sum()))
        hy = H / 2 - self.fy * math.tan(math.asin(max(-1, min(1, -f[1])))) if False else H / 2 - self.fy * (-f[1] / max(1e-6, math.sqrt(1 - f[1] ** 2)))
        below = np.arange(H)[:, None] > hy + 2
        holes = float(((rgb[..., 0] == 255) & (rgb[..., 1] == 0) & (rgb[..., 2] == 255) & below).mean()) * 100 if mode == 'holes' else None
        if vis_out is not None and pos and len(ids): vis_out.update(int(p) for p in vis_pc)
        if ret_img: res_img = rgb.copy()
        res = dict(tris=nt_all, drawn=drawn, holes=holes, ms=round((time.time() - t0) * 1000), eye=[round(float(v), 1) for v in eye], **stats)
        if ret_img: res['img'] = res_img
        if out:
            from PIL import Image, ImageDraw
            im = Image.fromarray(rgb).resize((W * 2, H * 2), Image.NEAREST); d = ImageDraw.Draw(im)
            try:
                from PIL import ImageFont
                fnt = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
            except Exception: fnt = None
            if mark:
                rel = tgt - eye; cx, cy, cz = rel @ s, rel @ u, rel @ f
                if cz > .3:
                    px, py = (W / 2 + self.fx * cx / cz) * 2, (H / 2 - self.fy * cy / cz) * 2
                    d.ellipse((px - 14, py - 14, px + 14, py + 14), outline=(255, 40, 40), width=3); d.line((px - 20, py, px + 20, py), fill=(255, 40, 40), width=2); d.line((px, py - 20, px, py + 20), fill=(255, 40, 40), width=2)
            txt = (label + ' ' if label else '') + f'({x:.0f},{y:.0f},{z:.0f}) h={heading:.2f} ' + (f'пурпур ниже горизонта {holes:.1f}%' if holes is not None else mode) + (f' · кусков видно {stats["vis_pieces"]} из {stats["pieces"]}, треуг. в видимых {stats["vis_piece_tris"]//1000}k из {stats["sub_tris"]//1000}k' if stats else '')
            d.rectangle((0, 0, W * 2, 18), fill=(0, 0, 0)); d.text((4, 2), txt, fill=(255, 255, 255), font=fnt)
            im.save(out)
        return res
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('level'); ap.add_argument('x', type=float); ap.add_argument('y', type=str, help='высота, м, или g — земля под точкой')
    ap.add_argument('z', type=float); ap.add_argument('heading', nargs='?', type=float, default=0.0); ap.add_argument('-o', default='shot.png'); ap.add_argument('--mode', default='normal', choices=['normal', 'holes'])
    ap.add_argument('--label', default=''); ap.add_argument('--top', action='store_true'); a = ap.parse_args()
    S = Shooter(a.level); y = (S.ground(a.x, a.z) or 0.0) if a.y == 'g' else float(a.y)
    print(S.shot(a.x, y, a.z, a.heading, a.o, a.label, a.mode, a.top))
