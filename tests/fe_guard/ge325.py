#!/usr/bin/env python3
"""Правка Роба 325 (повторы 244, 265, 293): «при наезде к газете в новой игре есть момент, когда часть пола будто пропадает» —
только на PSP. Модель GE на Маке + сверка с кадрами железа. Только чтение (fe.shr, кадры тура), без эмулятора.

  python3 tests/fe_guard/ge325.py --host НОВЫЙ --host-old ПРЕЖНИЙ [--fe build/fe.shr] [--hw build/psp-tour/20261004-2133]

Модель GE (как железо; эмулятор PPSSPP так не делает): срез по near (у нас GU_CLIP_PLANES), потом вершина дальше 2048 px от
центра экрана (защитная полоса, viewport 2048) — треугольник выбрасывается ЦЕЛИКОМ.
1) куски (вся геометрия гостиной, и пол floor3): перелёт NEW GAME шагом 0,25 кадра — видимая площадь выброшенных треугольников
   (свидетель: геометрию экспорт режет у камеры, её GE не теряет);
2) подсветки (FeBill: свет из окна window.bmp, конус лампы, отсвет телевизора, свет на потолке) — квады движка, их никто не
   резал. Для каждой позы всех перелётов (туда и обратно) и кадра меню: вершины как drawBill (frontend3d.c), срез —
   НАСТОЯЩИЙ код viewer/fe_billcut.h (tests/fe_guard/billcut_host.c; --host-old — сборка -DFE_BILL_CUT_OLD, квад как есть).
   «Потеряно» — видимая площадь (px) подсветки, которую GE выбросит; «лишнее/дыра» — разница площади нарисованного и
   идеального (квад, срезанный по near без полосы, как эмулятор и PS2): у веера должна быть 0;
3) кадры железа (--hw: shots/fe293_*.bmp тура TEST 10, fecap): пол floor3 + подсветки программной растеризацией в позе кадра
   (перспективные uv, MODULATE с цветом вершин, сложение подсветок), две гипотезы: «железо» (полоса выбрасывает) и «эмулятор»
   (рисует всё) — какая совпала с кадром.
ИТОГ зелёный: новое — 0 px потерь и 0 px лишнего на всех позах; прежнее — потери в перелёте NEW GAME (красный контроль пойман);
куски — 0 px; кадры железа (если есть) — гипотеза «железо» не хуже «эмулятора» на всех кадрах и лучше на кадрах после tl 35."""
import argparse, glob, math, os, re, struct, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GB = 2048.                      # защитная полоса GE, px от центра (sceGuViewport(2048, 2048, 480, 272))
F_ADD, F_BLEND, F_MENUHID = 4, 2, 16


class FE:
    def __init__(self, path):
        d = Path(path).read_bytes(); self.d = d
        h = struct.unpack_from('<4s13If2I12f3I', d, 0)
        (self.magic, self.version, self.size, self.nTex, self.offTex, self.nPiece, self.offPiece, self.nTrack, self.offTrack,
         self.nBill, self.offBill, self.nFrames, self.offCam, self.menuFrame) = h[:14]
        self.offTexNames = h[31]
        self.texnames = [d[self.offTexNames + 32 * i:self.offTexNames + 32 * i + 32].split(b'\0')[0].decode('latin1') for i in range(self.nTex)]
        self.pieces = []
        for i in range(self.nPiece):
            o = self.offPiece + 64 * i
            tex, ttr, fl, node, vis, _, nv, ov = struct.unpack_from('<6H2I', d, o)
            f = struct.unpack_from('<4f6fI', d, o + 20)
            self.pieces.append(dict(i=i, tex=tex, fl=fl, node=node, vis=vis, nv=nv, ov=ov, origin=np.array(f[0:3]), scale=f[3]))
        self.cam = np.frombuffer(d, '<f4', self.nFrames * 12, self.offCam).reshape(-1, 12).astype(np.float64)
        self.tracks = [struct.unpack_from('<IIfII', d, self.offTrack + 32 * i) for i in range(self.nTrack)]
        t = struct.unpack_from('<4sIII', d, len(d) - 16)
        self.flights = [struct.unpack_from('<BBHHHHHf', d, t[1] + 16 * k) for k in range(t[2])] if t[0] == b'FLT1' else []

    def verts(self, p):
        q = np.frombuffer(self.d, np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')]), p['nv'], p['ov'])
        s = p['scale'] * (32768. / 32767.) / 32768.
        P = np.stack([q['x'], q['y'], q['z']], 1).astype(np.float64) * s + p['origin']
        UV = np.stack([q['u'].astype(np.uint16), q['v'].astype(np.uint16)], 1).astype(np.float64) / 256.
        c = q['c'].astype(np.uint64); C = np.c_[c & 255, (c >> 8) & 255, (c >> 16) & 255, (c >> 24) & 255].astype(np.float64) / 255.
        return P, UV, C

    def tex(self, t, lev=0):
        d = self.d; o = self.offTex + 64 * t
        w, h, nlev = struct.unpack_from('<HHB', d, o); oc, = struct.unpack_from('<I', d, o + 8)
        offs = struct.unpack_from('<8I', d, o + 12); bufw = struct.unpack_from('<8H', d, o + 44)
        pal = np.frombuffer(d, np.uint8, 1024, oc).reshape(256, 4); lw, lh = w, h
        for _ in range(lev): lw, lh = max(1, lw // 2), max(1, lh // 2)
        rb = bufw[lev]; hp = (lh + 7) & ~7
        raw = np.frombuffer(d, np.uint8, rb * hp, offs[lev]).reshape(hp // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(hp, rb)[:lh, :lw]
        return pal[raw].astype(np.float64) / 255.

    def view(self, tl):   # как feDraw: камера между кадрами данных линейно; Hor+ 16:9
        f0 = int(tl); f1 = min(f0 + 1, self.nFrames - 1); c = self.cam[f0] + (self.cam[f1] - self.cam[f0]) * (tl - f0)
        pos = c[:3]; fw = c[3:6] / np.linalg.norm(c[3:6]); r = np.cross(fw, c[6:9]); r /= np.linalg.norm(r); u = np.cross(r, fw)
        tvy = math.tan(c[9] * .5) * .75
        return pos, fw, r, u, tvy * 16 / 9, tvy, c[10]

    def bills(self, tl, sel=-1, clock=0.):
        """квады подсветок, как drawBill (frontend3d.c): вершины в порядке полосы 0 1 2 3"""
        d = self.d; pos, fw, r, u, tvx, tvy, near = self.view(tl); out = []
        for i in range(self.nBill):
            tr_, tex, fl, mode, glow = struct.unpack_from('<3H2B', d, self.offBill + 80 * i)
            w, hh, abgr = struct.unpack_from('<2fI', d, self.offBill + 80 * i + 8)
            M = np.array(struct.unpack_from('<12f', d, self.offBill + 80 * i + 20)).reshape(3, 4)
            if glow != 0xff and glow != sel: continue
            col = np.array([(abgr >> s) & 255 for s in (0, 8, 16, 24)], float) / 255.
            if tr_ != 0xffff:
                typ, nf, fps, tfl, off = self.tracks[tr_]
                v = struct.unpack_from('<6f', d, off + 24 * (int(clock * fps) % nf)); w, hh = v[:2]; col = np.clip(np.array(v[2:]), 0, 1)
            o = M[:, 3].copy()
            if glow != 0xff: t = pos - o; o += t / np.linalg.norm(t) * .05      # FE_GLOW_LIFT
            if mode == 0: ax, ay = M[:, 0], M[:, 1]
            elif mode == 1:
                ay = M[:, 1] / np.linalg.norm(M[:, 1]); tc = pos - o; ax = np.cross(ay, tc); ax /= np.linalg.norm(ax)
            else: ax, ay = r, u
            sx = np.array([-.5, .5, -.5, .5]); sy = np.array([.5, .5, -.5, -.5])
            P = o + ax * (sx * w)[:, None] + ay * (sy * hh)[:, None]
            out.append(dict(i=i, tex=tex, fl=fl, P=P, UV=np.array([[0, 0], [1, 0], [0, 1], [1, 1]], float), col=col, name=self.texnames[tex]))
        return out


def cam_xyz(F, tl, P):
    pos, fw, r, u, tvx, tvy, near = F.view(tl); rel = P - pos
    return np.c_[rel @ r, rel @ u, rel @ fw]


def clip_near(V, near):
    out = []
    for i in range(len(V)):
        a, b = V[i], V[(i + 1) % len(V)]
        if a[2] >= near: out.append(a)
        if (a[2] >= near) != (b[2] >= near): out.append(a + (b - a) * ((near - a[2]) / (b[2] - a[2])))
    return out


def area_on_screen(sx, sy):
    """площадь многоугольника (экранные px относительно центра) внутри экрана 480×272"""
    p = list(zip(sx, sy))
    for k, lim, sgn in ((0, 240, 1), (0, 240, -1), (1, 136, 1), (1, 136, -1)):
        q = []
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]; fa, fb = sgn * a[k] - lim, sgn * b[k] - lim
            if fa <= 0: q.append(a)
            if (fa <= 0) != (fb <= 0): t = fa / (fa - fb); q.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        p = q
        if len(p) < 3: return 0.
    x = np.array([v[0] for v in p]); y = np.array([v[1] for v in p])
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2


def ge_tri(F, tl, V3, band=True):
    """треугольник (3 вершины в осях камеры [+атрибуты]) -> (видимая площадь px, выброшен ли GE, наибольшее удаление px)"""
    pos, fw, r, u, tvx, tvy, near = F.view(tl)
    poly = clip_near(list(V3), near)
    if len(poly) < 3: return 0., False, 0.
    poly = np.array(poly); z = poly[:, 2]
    sx = poly[:, 0] / z / tvx * 240; sy = poly[:, 1] / z / tvy * 136
    a = area_on_screen(sx, sy); far = float(max(np.abs(sx).max(), np.abs(sy).max()))
    return a, bool(band and far >= GB), far


def host_cut(F, host, items):
    """items: [(tl, bill)] -> ответы среза (−1 или список вершин мира+uv) из настоящего кода fe_billcut.h"""
    lines = []
    for tl, b in items:
        pos, fw, r, u, tvx, tvy, near = F.view(tl)
        v = list(pos) + list(r) + list(u) + list(fw) + [tvx, tvy, near] + list(b['P'].ravel()) + list(b['UV'].ravel())
        lines.append(' '.join(f'{x:.9g}' for x in v))
    out = subprocess.run([host], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout.split('\n')
    res = []
    for ln in out[:len(items)]:
        a = ln.split(); n = int(a[0])
        res.append(-1 if n < 0 else np.array([float(x) for x in a[1:]]).reshape(n, 5))
    return res


def bill_fate(F, tl, b, cut):
    """-> (идеальная видимая площадь, нарисованная GE, потерянная) для подсветки b при ответе среза cut"""
    V = cam_xyz(F, tl, b['P'])
    ideal = sum(ge_tri(F, tl, V[t], band=False)[0] for t in ([0, 1, 2], [2, 1, 3]))
    if isinstance(cut, int):                        # полоса: два треугольника как есть
        tris = [V[[0, 1, 2]], V[[2, 1, 3]]]
    else:                                           # веер
        W = cam_xyz(F, tl, cut[:, :3]); tris = [W[[0, j, j + 1]] for j in range(1, len(W) - 1)]
    drawn = lost = 0.
    for t in tris:
        a, drop, far = ge_tri(F, tl, t)
        if drop: lost += a
        else: drawn += a
    return ideal, drawn, lost


def poses(F):
    """позы: кадр меню + все перелёты туда/обратно (NEW GAME шагом 0,25, прочие 0,5); подсветка пункта — только в кадре меню"""
    P = [('menu', float(F.menuFrame), -1)] + [('menu', float(F.menuFrame), g) for g in range(6)]
    for f in F.flights:
        item, fl, _, go0, go1, b0, b1, deg = f
        st = .25 if item == 4 else .5
        for tl in np.arange(go0, go1 + 1e-6, st): P.append((f'item{item}', float(tl), -1))
        if fl & 1 and b1 > b0:
            for tl in np.arange(b0, b1 + 1e-6, st): P.append((f'item{item}back', float(tl), -1))
    return P


def bills_check(F, host, label):
    items, meta = [], []
    for name, tl, sel in poses(F):
        for clock in (0., .37, .81):                # дорожки размера/цвета подсветок идут по часам гостиной — несколько фаз
            for b in F.bills(tl, sel, clock):
                if sel >= 0 and b['name'].find('glow') < 0: continue   # кадр меню с подсветкой пункта — только сама подсветка
                items.append((tl, b)); meta.append((name, tl, b['i'], b['name']))
    cuts = host_cut(F, host, items)
    worst = {}; tot_lost = tot_bad = max_bad = 0.; ng = []; ncut = 0; where_bad = None
    for (tl, b), (name, _, bi, bn), cut in zip(items, meta, cuts):
        ideal, drawn, lost = bill_fate(F, tl, b, cut)
        bad = abs(drawn + lost - ideal)              # дыра/наложение веера против идеального среза
        ncut += not isinstance(cut, int)
        tot_lost += lost; tot_bad += bad
        if bad > max_bad: max_bad, where_bad = bad, (name, tl, bn)
        k = (name, bi)
        if lost > worst.get(k, (0, 0))[0]: worst[k] = (lost, tl, bn)
        if name == 'item4' and lost > 0.5: ng.append((tl, bi, bn, lost))
    print(f'  {label}: поз×подсветок {len(items)}, нарезано {ncut}; потеряно GE {tot_lost:.0f} px (сумма по позам); лишнее/дыра веера против '
          f'идеального среза: сумма {tot_bad:.1f} px, наибольшее на позу {max_bad:.2f} px' + (f' ({where_bad[0]} tl {where_bad[1]:.2f} {where_bad[2]})' if where_bad and max_bad > .01 else ''))
    for (name, bi), (lost, tl, bn) in sorted(worst.items(), key=lambda x: -x[1][0])[:8]:
        if lost > 0.5: print(f'    {name:10s} подсветка #{bi} {bn:16s} худшая поза tl {tl:6.2f}: потеряно {lost:6.0f} px')
    if ng:
        first = {}
        for tl, bi, bn, lost in ng: first.setdefault((bi, bn), tl)
        print('    NEW GAME, с какого кадра железо теряет: ' + ', '.join(f'#{bi} {bn} с tl {tl:.2f}' for (bi, bn), tl in sorted(first.items(), key=lambda x: x[1])))
    return tot_lost, max_bad, ng


def pieces_check(F):
    go = next(f for f in F.flights if f[0] == 4)
    stat, node = [], []
    for p in F.pieces:
        if p['vis'] != 0xffff: continue
        P, UV, C = F.verts(p); (node if p['node'] != 0xffff else stat).append((p, P.reshape(-1, 3, 3)))
    S = np.concatenate([T for p, T in stat]); tot = 0.; worst = (0., 0.); nmax = 0.; nstr = 0
    for tl in np.arange(go[3], go[4] + 1e-6, .25):
        Ts = [S]
        for p, T in node:
            typ, nf, fps, tfl, off = F.tracks[p['node']]; k = min(int(tl), nf - 1) if tfl & 2 else 0
            M = np.frombuffer(F.d, '<f4', 12, off + 48 * k).reshape(3, 4).astype(np.float64); Ts.append(T @ M[:, :3].T + M[:, 3])
        T = np.concatenate(Ts); pos, fw, r, u, tvx, tvy, near = F.view(tl); rel = T - pos
        x, y, z = rel @ r, rel @ u, rel @ fw
        out = (z < near).all(1) | (x > tvx * z).all(1) | (-x > tvx * z).all(1) | (y > tvy * z).all(1) | (-y > tvy * z).all(1)
        front = (z >= near).all(1) & ~out; zz = np.maximum(z, 1e-9)
        far = np.maximum(np.abs(x / zz / tvx * 240), np.abs(y / zz / tvy * 136)).max(1)
        if front.any(): nmax = max(nmax, float(far[front].max()))
        cand = np.nonzero((front & (far >= GB)) | (~out & ~front))[0]; nstr += int((~out & ~front).sum()); a = 0.
        for k in cand:
            ar, drop, _ = ge_tri(F, tl, np.c_[x[k], y[k], z[k]])
            if drop: a += ar
        tot += a
        if a > worst[0]: worst = (a, tl)
    print(f'  куски (геометрия, пол floor3 — один из них), NEW GAME шагом 0,25: выброшено видимой площади {tot:.0f} px; '
          f'пересекают near {nstr}; наибольшее удаление вершины {nmax:.0f} px из 2048')
    return tot


def render_floor_and_bills(F, tl, W=480, H=272):
    """программная растеризация: пол floor3 (MODULATE с цветом вершин) и вклад подсветок со сложением по треугольникам
    -> (пол, маска пола, вклад «железо», вклад «эмулятор»)"""
    t = F.texnames.index('floor3.bmp'); T0 = F.tex(t)
    img = np.zeros((H, W, 3)); msk = np.zeros((H, W), bool); zb = np.zeros((H, W))
    pos, fw, r, u, tvx, tvy, near = F.view(tl)

    def raster(V, attr, cb):
        z = V[:, 2]; sx = W / 2 + V[:, 0] / z / tvx * W / 2; sy = H / 2 - V[:, 1] / z / tvy * H / 2
        x0, x1 = max(0, int(sx.min())), min(W - 1, int(math.ceil(sx.max()))); y0, y1 = max(0, int(sy.min())), min(H - 1, int(math.ceil(sy.max())))
        if x0 > x1 or y0 > y1: return
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        d = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(d) < 1e-9: return
        l1 = ((gx - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (gy - sy[0])) / d
        l2 = ((sx[1] - sx[0]) * (gy - sy[0]) - (gx - sx[0]) * (sy[1] - sy[0])) / d
        l0 = 1 - l1 - l2; m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any(): return
        iw = np.stack([l0 / z[0], l1 / z[1], l2 / z[2]], -1)[m]; zz = iw.sum(-1); ww = iw / zz[:, None]
        yy, xx = np.nonzero(m); cb(yy + y0, xx + x0, zz, ww @ attr)

    for p in F.pieces:
        if p['tex'] != t or p['vis'] != 0xffff: continue
        P, UV, C = F.verts(p); V = cam_xyz(F, tl, P); A = np.c_[UV, C]
        for k in range(0, len(P), 3):
            poly = clip_near(list(np.c_[V[k:k + 3], A[k:k + 3]]), near)
            for j in range(1, len(poly) - 1):
                tri = np.array([poly[0], poly[j], poly[j + 1]])

                def put(yy, xx, zz, a):
                    th, tw = T0.shape[:2]; x = a[:, 0] * tw - .5; y = a[:, 1] * th - .5
                    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
                    g = lambda yy_, xx_: T0[yy_ % th, xx_ % tw]
                    s = g(y0, x0) * (1 - fx) * (1 - fy) + g(y0, x0 + 1) * fx * (1 - fy) + g(y0 + 1, x0) * (1 - fx) * fy + g(y0 + 1, x0 + 1) * fx * fy
                    img[yy, xx] = s[:, :3] * a[:, 2:5]; msk[yy, xx] = True; zb[yy, xx] = zz
                raster(tri[:, :3], tri[:, 3:], put)
    add = {True: np.zeros((H, W, 3)), False: np.zeros((H, W, 3))}
    texc = {}
    for b in F.bills(tl):
        if not (b['fl'] & F_ADD): continue
        if b['tex'] not in texc: texc[b['tex']] = F.tex(b['tex'])
        TB = texc[b['tex']]; V = cam_xyz(F, tl, b['P'])
        for tri in ([0, 1, 2], [2, 1, 3]):
            a, drop, far = ge_tri(F, tl, V[tri])
            poly = clip_near(list(np.c_[V[tri], b['UV'][tri]]), near)
            for j in range(1, len(poly) - 1):
                tt = np.array([poly[0], poly[j], poly[j + 1]])

                def put(yy, xx, zz, a2, drop=drop):
                    ok = zz >= np.where(msk[yy, xx], zb[yy, xx], 0) * .999       # GEQUAL по 1/z против пола
                    th, tw = TB.shape[:2]
                    c = TB[np.clip((a2[:, 1] * th).astype(int), 0, th - 1), np.clip((a2[:, 0] * tw).astype(int), 0, tw - 1), :3] * b['col'][:3]
                    for hw_ in (True, False):
                        if hw_ and drop: continue
                        add[hw_][yy[ok], xx[ok]] += c[ok]
                raster(tt[:, :3], tt[:, 3:], put)
    return img, msk, add[True], add[False]


def frame_models(F, fn):
    """кадр fecap -> (tl, ошибки: только пол, +подсветки «железо», +подсветки «эмулятор»; яркость низа экрана) или None"""
    from PIL import Image
    tl = int(re.search(r'_(\d{4})\.bmp$', fn).group(1)) / 100.
    hw = np.asarray(Image.open(fn).convert('RGB')).astype(float)
    img, msk, a_hw, a_emu = render_floor_and_bills(F, tl)
    teal = (hw[..., 1] > hw[..., 0] + 15) & (hw[..., 1] > hw[..., 2]); win = np.zeros_like(msk); win[40:235, 40:440] = True
    m = msk & teal & win
    low = float(hw[150:250, 40:440].mean())
    if m.sum() < 2000: return tl, None, low
    return tl, [float(np.abs(np.clip((img + a) * 255, 0, 255)[m] - hw[m]).mean()) for a in (0, a_hw, a_emu)], low


def verdict(e):
    return '-' if e is None else 'железо' if e[1] < e[2] - 1 else 'эмулятор' if e[2] < e[1] - 1 else 'обе'


def hw_check(F, d, pat='fe293_*.bmp'):
    fs = sorted(glob.glob(str(Path(d) / 'shots' / pat)))
    if not fs: print(f'  кадров {pat} нет в {d}/shots — сверка с железом пропущена'); return None
    print('  кадр железа        tl   ошибка (сред. |Δ| по полу, из 255): только пол | +подсветки «железо» | +подсветки «эмулятор»')
    ok = True; late = 0
    for fn in fs:
        tl, e, low = frame_models(F, fn)
        if e is None: continue
        print(f'  {os.path.basename(fn):18s} {tl:5.2f}   {e[0]:5.1f} | {e[1]:5.1f} | {e[2]:5.1f}   {verdict(e)}')
        if e[1] > e[2] + 1: ok = False
        if tl >= 35 and e[1] < e[2] - 10: late += 1
    print(f'  кадры железа: гипотеза «железо (полоса выбрасывает подсветку)» {"не хуже на всех кадрах" if ok else "ХУЖЕ на части кадров"}; '
          f'кадров после tl 35, где она лучше «эмулятора» больше чем на 10: {late}')
    return ok and late > 0


def emu_check(F, new_dir, old_dir):
    """покадровый перелёт NEW GAME в безголовом эмуляторе (программная отрисовка PPSSPP выбрасывает треугольник за полосой, как
    железо): кадры fe265_b_<tl×100>.bmp нового и прежнего — с какой гипотезой совпал кадр; скачок яркости низа экрана (пол)"""
    out = {}
    for lab, dd in (('новое', new_dir), ('прежнее', old_dir)):
        fs = sorted(glob.glob(str(Path(dd) / 'fe265_b_*.bmp')))
        fs = [f for f in fs if int(re.search(r'_(\d{4})\.bmp$', f).group(1)) >= 2500]
        if not fs: print(f'  {lab}: кадров fe265_b_*.bmp нет в {dd}'); out[lab] = None; continue
        hwv = []; jumps = []; prev = None; line = []
        for fn in fs:
            tl, e, low = frame_models(F, fn); v = verdict(e)
            if prev is not None and abs(low - prev) > 12: jumps.append((tl, low - prev))
            prev = low
            if v == 'железо': hwv.append(tl)
            line.append(f'{tl:.1f}:{v[0] if v != "-" else "-"}')
        out[lab] = dict(hw=hwv, jumps=jumps, n=len(fs))
        print(f'  {lab}: кадров (tl ≥ 25) {len(fs)}; совпали с «железо» (свет выброшен): {len(hwv)}'
              + (f" (tl {', '.join(f'{t:.1f}' for t in hwv[:10])}{' …' if len(hwv) > 10 else ''})" if hwv else '')
              + f"; скачков яркости пола > 12: {len(jumps)}" + (' (' + ', '.join(f'tl {t:.1f}: {x:+.0f}' for t, x in jumps) + ')' if jumps else ''))
        print('    ' + ' '.join(line) + '   (ж — железо, э — эмулятор/всё, о — обе)')
    n, o = out.get('новое'), out.get('прежнее')
    if not n or not o: return False
    ok = not n['hw'] and not n['jumps'] and len(o['hw']) >= 3
    print(f"  эмулятор: новое {'без потерь и скачков' if not n['hw'] and not n['jumps'] else 'ТЕРЯЕТ/СКАЧЕТ'}; прежнее "
          f"{'теряет свет (красный пойман)' if len(o['hw']) >= 3 else 'НЕ теряет — красный НЕ пойман'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fe', default=str(ROOT / 'build/fe.shr')); ap.add_argument('--host', required=True); ap.add_argument('--host-old', required=True)
    ap.add_argument('--hw'); ap.add_argument('--emu-new'); ap.add_argument('--emu-old'); a = ap.parse_args()
    F = FE(a.fe); print(f'fe.shr {a.fe} ({len(F.d)} Б): кусков {F.nPiece}, подсветок {F.nBill}, перелётов {len(F.flights)}')
    print('1) куски (геометрия):'); pl = pieces_check(F)
    print('2) подсветки — прежнее (квад как есть, -DFE_BILL_CUT_OLD):'); ol, ob, ong = bills_check(F, a.host_old, 'прежнее')
    print('   подсветки — новое (срез по пирамиде полосы, viewer/fe_billcut.h):'); nl, nb, nng = bills_check(F, a.host, 'новое')
    hw = None
    if a.hw:
        print(f'3) кадры железа {a.hw}:'); hw = hw_check(F, a.hw)
    emu = None
    if a.emu_new and a.emu_old:
        print('4) безголовый эмулятор, покадровый перелёт NEW GAME (новое против прежнего):'); emu = emu_check(F, a.emu_new, a.emu_old)
    red = sum(x[3] for x in ong) > 1000.
    ok = nl < 0.5 and nb <= 1.0 and pl < 0.5 and red and hw is not False and emu is not False
    print(f'ИТОГ: {"зелёный" if ok else "КРАСНЫЙ"} — новое: потеряно {nl:.0f} px, лишнее/дыра не больше {nb:.2f} px на позу; прежнее: потеряно в NEW GAME '
          f'{sum(x[3] for x in ong):.0f} px ({"красный контроль пойман" if red else "КРАСНЫЙ НЕ ПОЙМАН"}); куски {pl:.0f} px'
          + ('' if hw is None else f'; кадры железа: {"модель совпала" if hw else "НЕ СОВПАЛА"}')
          + ('' if emu is None else f'; эмулятор: {"новое чистое, прежнее теряет" if emu else "НЕ СХОДИТСЯ"}'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
