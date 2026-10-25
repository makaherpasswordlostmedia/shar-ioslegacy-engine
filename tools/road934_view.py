#!/usr/bin/env python3
"""№934, проверка дальних дорог и мостов (tests/road934/*.sh). Общие куски: настоящие (полные) треугольники дорог/мостов уровня как эталон, чтение road934.shr независимо от экспортёра,
программная проекция на кадр 480×272 (та же камера, что у движка: sceGumLookAt вверх (0,1,0), sceGumPerspective(fovY, 16/9)), выбор точек обзора, сценарий эмулятора, метрики масок.

  road934_view.py pick LEVEL.shr N [--names J] [--fov 55] [--dmin 270] [--dmax 500]   -> строки «x y z az» (глаз = дорога + 2,3 м, az — градусы от -Z к +X)
  road934_view.py data LEVEL.shr ROAD934.shr [--names J] [--views 24] [--red]          -> гейт данных: пересечение/объединение масок настоящих и упрощённых треугольников (код 0 = OK)
  road934_view.py scen LEVEL N VIEWS.txt                                               -> сценарий эмулятора на уровень (кадры: a = слой пурпуром, b = слой обычный, c = слоя нет)
  road934_view.py shots LEVEL.shr DIR VIEWS.txt [--names J] [--red]                    -> метрики по кадрам эмулятора (код 0 = OK)"""
import argparse, math, re, struct, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import road934_export as X
import shr7read

W, H = 480, 272
ASPECT = 16.0 / 9.0
EYE_H = 30.0     # глаз над дорогой, м: над крышами и деревьями; дальше 12 м над землёй движок берёт даль 250 м (far909.h)
PITCH = -0.05    # наклон взгляда (y компоненты вектора взгляда)
NAMES_DEFAULT = ['build/roads/texnames.json', '/Users/USER/Downloads/shar-psp-roads-w/build/roads/texnames.json']


def names_path(a):
    if a: return a
    for p in NAMES_DEFAULT:
        if Path(p).exists(): return p
    return ''


def truth(level, names):
    Pq, G, tm, vc, isbr, nm, nr, nb = X.select(level, names, '')
    return Pq, isbr


def read_rd34(path):
    """RD35 -> (N,3,3) мировые треугольники (читаем независимо от экспортёра: цели проверки — формат и квантование)"""
    b = Path(path).read_bytes(); assert b[:4] == b'RD35', 'не RD35'
    nb, ntri, nv = struct.unpack_from('<III', b, 4); ox, oy, oz, E = struct.unpack_from('<4f', b, 16)
    voff = 32 + 32 * nb; voff += -voff % 16
    v = np.frombuffer(b, np.uint8, 8 * nv, voff).reshape(nv, 8)
    xyz = v[:, 2:8].copy().view('<i2').reshape(nv, 3).astype(np.float64) * (E / 32768.0) + np.array([ox, oy, oz])
    out = []
    for i in range(nb):
        x0, y0, z0, x1, y1, z1, ioff, ni = struct.unpack_from('<6f2I', b, 32 + 32 * i)
        idx = np.frombuffer(b, '<u2', ni, ioff).reshape(-1, 3)
        assert int(idx.max()) < nv, 'индекс за пределами вершин'
        out.append(xyz[idx])
    r = np.concatenate(out) if out else np.zeros((0, 3, 3)); assert len(r) == ntri
    return r


def camera(eye, az_deg, fov, pitch=PITCH):
    a = math.radians(az_deg)
    f = np.array([math.sin(a), pitch, -math.cos(a)]); f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    return np.asarray(eye, float), f, r, u, math.tan(math.radians(fov) / 2)


def project(P, cam):
    eye, f, r, u, th = cam
    d = P - eye
    xc = d @ r; yc = d @ u; zc = d @ f
    with np.errstate(divide='ignore', invalid='ignore'):
        px = (xc / (zc * th * ASPECT) * .5 + .5) * W; py = (.5 - yc / (zc * th) * .5) * H
    return px, py, zc


def _clip_near(cs, zmin=1.0):
    """многоугольник в координатах камеры (k,3) -> срез по zc >= zmin (Сазерленд-Ходжман); GE режет по ближней плоскости так же, большие треугольники слоя не пропадают целиком"""
    out = []
    for i in range(len(cs)):
        a, b = cs[i], cs[(i + 1) % len(cs)]
        ina, inb = a[2] >= zmin, b[2] >= zmin
        if ina: out.append(a)
        if ina != inb:
            t = (zmin - a[2]) / (b[2] - a[2]); out.append(a + (b - a) * t)
    return out


def raster(P, cam, dmin, dmax):
    """маска (H,W): пиксели треугольников, у которых точка попадает в кольцо [dmin, dmax] по расстоянию в плане ОТ ГЛАЗА. Расстояние считается по пикселю (перспективно-верная глубина),
    а не по центру треугольника: большой упрощённый треугольник слоя режется кольцом так же, как мелкие треугольники эталона (иначе метрика сравнивала бы разные вещи).
    Треугольники срезаются по ближней плоскости zc >= 1 м (как видеочип)."""
    eye, f, r, u, th = cam
    m = np.zeros((H, W), bool)
    if not len(P): return m
    # грубый отсев: ближайшая точка рамки треугольника в плане дальше dmax, либо все вершины позади глаза
    lo = P[:, :, [0, 2]].min(1); hi = P[:, :, [0, 2]].max(1); e2 = eye[[0, 2]]
    nd = np.hypot(np.maximum(np.maximum(lo[:, 0] - e2[0], e2[0] - hi[:, 0]), 0), np.maximum(np.maximum(lo[:, 1] - e2[1], e2[1] - hi[:, 1]), 0))
    P = P[nd <= dmax]
    if not len(P): return m
    d = P - eye; xc = d @ r; yc = d @ u; zc = d @ f
    alive = (zc > 1.0).any(1)
    xc, yc, zc = xc[alive], yc[alive], zc[alive]
    th_a = th * ASPECT
    for t in range(len(zc)):
        cs = np.stack([xc[t], yc[t], zc[t]], 1)
        poly = [c for c in cs] if (zc[t] >= 1.0).all() else _clip_near(list(cs))
        if len(poly) < 3: continue
        poly = np.array(poly)
        sx = poly[:, 0] / (poly[:, 2] * th_a); sy = poly[:, 1] / (poly[:, 2] * th)
        px = (sx * .5 + .5) * W; py = (.5 - sy * .5) * H; z = poly[:, 2]
        x0, x1 = max(0, int(math.floor(px.min()))), min(W - 1, int(math.ceil(px.max())))
        y0, y1 = max(0, int(math.floor(py.min()))), min(H - 1, int(math.ceil(py.max())))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        for k in range(1, len(poly) - 1):
            X, Y, Z = px[[0, k, k + 1]], py[[0, k, k + 1]], z[[0, k, k + 1]]
            dd = (Y[1] - Y[2]) * (X[0] - X[2]) + (X[2] - X[1]) * (Y[0] - Y[2])
            if abs(dd) < 1e-9: continue
            a = ((Y[1] - Y[2]) * (gx - X[2]) + (X[2] - X[1]) * (gy - Y[2])) / dd
            b = ((Y[2] - Y[0]) * (gx - X[2]) + (X[0] - X[2]) * (gy - Y[2])) / dd
            c = 1 - a - b
            e = -1e-6
            inside = (a >= e) & (b >= e) & (c >= e)
            if not inside.any(): continue
            invz = a / Z[0] + b / Z[1] + c / Z[2]
            with np.errstate(divide='ignore', invalid='ignore'): zz = 1.0 / invz
            qx = (gx / W - .5) * 2 * th_a; qy = (.5 - gy / H) * 2 * th
            ray = f[None, None, :] + qx[..., None] * r + qy[..., None] * u
            dist = zz * np.hypot(ray[..., 0], ray[..., 2])
            m[y0:y1 + 1, x0:x1 + 1] |= inside & (dist >= dmin) & (dist <= dmax)
    return m


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def pick(Pq, isbr, n, fov=55.0, dmin=270.0, dmax=500.0, sep=220.0, seed=1, ncand=500):
    A = 0.5 * np.linalg.norm(np.cross(Pq[:, 1] - Pq[:, 0], Pq[:, 2] - Pq[:, 0]), axis=1)
    cen = Pq.mean(1)
    rng = np.random.default_rng(seed)
    road = np.nonzero(isbr == 0)[0]
    cand = rng.choice(road, min(ncand, len(road)), replace=False)
    hf = math.degrees(2 * math.atan(math.tan(math.radians(fov / 2)) * ASPECT))
    res = []
    for c in cand:
        e = cen[c] + np.array([0, EYE_H, 0])
        d = cen[:, [0, 2]] - e[[0, 2]]; dist = np.hypot(d[:, 0], d[:, 1]); az = np.degrees(np.arctan2(d[:, 0], -d[:, 1]))
        near = (dist > dmin) & (dist < dmax)
        for a0 in range(0, 360, 15):
            da = (az - a0 + 180) % 360 - 180
            res.append((float(A[near & (np.abs(da) < hf / 2)].sum()), e, a0))
    res.sort(key=lambda t: -t[0])
    out = []
    for s, e, a0 in res:
        if any(np.hypot(e[0] - o[0][0], e[2] - o[0][2]) < sep for o in out): continue
        out.append((e, a0, s))
        if len(out) >= n: break
    return out


def dmetrics(Pa, Pb, views, fov, dmin, dmax):
    """пересечение/объединение масок двух наборов треугольников по видам; возвращает список (iou, площадь A, площадь B)"""
    res = []
    for e, a0, _ in views:
        cam = camera(e, a0, fov)
        ma = raster(Pa, cam, dmin, dmax); mb = raster(Pb, cam, dmin, dmax)
        u = (ma | mb).sum()
        res.append(((ma & mb).sum() / u if u else 1.0, int(ma.sum()), int(mb.sum())))
    return res


def read_views(path):
    out = []
    for ln in Path(path).read_text().splitlines():
        t = ln.split()
        if len(t) >= 4 and not ln.startswith('#'): out.append((np.array([float(t[0]), float(t[1]), float(t[2])]), int(t[3]), float(t[4]) if len(t) > 4 else 0.0))
    return out


def scenario(level, views, fov):
    """сценарий эмулятора: на каждый вид кадры a (слой пурпуром), b (слой обычный), c (слоя нет)"""
    L = ['wait 12', 'scene LOAD', 'flag golevel %d' % level, 'wait 40', 'flag cfgdefaults 1', 'scene FOOT', 'wait 6', 'flag stop']
    for i, (e, a0, _) in enumerate(views):
        a = math.radians(a0)
        L += ['scene v%d' % i, 'foot %.1f %.1f 0.0' % (e[0], e[2]), 'waitload 25', 'cam %.1f %.2f %.1f %.4f %.4f %.4f %.1f' % (e[0], e[1], e[2], math.sin(a), PITCH, -math.cos(a), fov),
              'wait 1', 'flag farroad934cache 0', 'wait 7', 'flag farroad934cache 1', 'wait 7', 'flag farroad934cache 0', 'flag farroad934dbg 1', 'wait 3', 'shot L%dv%d_a' % (level, i), 'flag farroad934dbg 0', 'wait 2', 'shot L%dv%d_b' % (level, i),
              'flag farroad934 0', 'wait 3', 'shot L%dv%d_c' % (level, i), 'flag farroad934 1']
    L += ['cam off', 'wait 1', 'end']
    return '\n'.join(L) + '\n'


def load_png(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB').crop((0, 0, W, H)), np.int16)


def magenta(img, tol=24):
    return (img[:, :, 0] >= 255 - tol) & (img[:, :, 1] <= tol) & (img[:, :, 2] >= 255 - tol)


def read_poses(smoke):
    """строки ROAD934 pose из журнала: [(t, eye, fwd, fovy, dd)]"""
    out = []
    for ln in Path(smoke).read_text(errors='replace').splitlines():
        m = re.match(r'ROAD934 pose t=([\d.]+) eye=([-\d.]+),([-\d.]+),([-\d.]+) fwd=([-\d.]+),([-\d.]+),([-\d.]+) fovy=([\d.]+) dd=([\d.]+)', ln)
        if m:
            v = [float(x) for x in m.groups()]; out.append((v[0], np.array(v[1:4]), np.array(v[4:7]), v[7], v[8]))
    return out


def shot_times(outdir):
    t = {}
    for ln in (Path(outdir) / 'twins_shots.tsv').read_text().splitlines():
        c = ln.split('\t')
        if len(c) >= 3: t[c[0]] = float(c[2])
    return t


def cam_from_pose(eye, fwd, fov):
    f = fwd / np.linalg.norm(fwd)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    return eye, f, r, u, math.tan(math.radians(fov) / 2)


def shots_metrics(level, outdir, views, names, fov, dd, cmin, red=False):
    """-> список по видам: dict(m_a, m_c, prec, cov, changed, truth). Поза кадра — из журнала движка (ROAD934 pose, гейт сам не гадает, где встала камера); outdir: L{N}v{i}_{a,b,c}.png, smoke.txt, twins_shots.tsv"""
    Pq, isbr = truth(level, names)
    d = shr7read.load(level, far=False, owner=0)
    OP = d['P'][(d['FL'] & 7) == 0]; ocen = OP.mean(1)
    poses = read_poses(Path(outdir) / 'smoke.txt')
    clusters = []   # пачки поз: слой пурпуром включён только на время кадра a каждого вида, паузы между пачками > 2 с (время журнала движка не равно времени twins_shots.tsv)
    for p in poses:
        if clusters and p[0] - clusters[-1][-1][0] < 2.0: clusters[-1].append(p)
        else: clusters.append([p])
    res = []
    for i, (e0, a0, _) in enumerate(views):
        fa = sorted(Path(outdir).glob('L*v%d_a*.png' % i)); fb = sorted(Path(outdir).glob('L*v%d_b*.png' % i)); fc = sorted(Path(outdir).glob('L*v%d_c*.png' % i))
        if not (fa and fb and fc): res.append(None); continue
        if i >= len(clusters): res.append(None); continue
        _, eye, fwd, fv, ddp = clusters[i][-1]   # последняя поза пачки (слой пурпуром включён только на время кадра a)
        A, B, C = load_png(fa[0]), load_png(fb[0]), load_png(fc[0])
        if red: A = C   # красный контроль: кадр «слоя нет» вместо кадра со слоем — охват обязан упасть
        M = magenta(A); Mc = magenta(C)
        cam = cam_from_pose(eye, fwd, fv)
        Tfar = raster(Pq, cam, ddp + 8.0, 500.0); Tall = raster(Pq, cam, max(60.0, ddp - 40.0), 560.0)
        near = np.hypot(ocen[:, 0] - eye[0], ocen[:, 2] - eye[2]) <= ddp
        Occ = dilate(raster(OP[near], cam, 0.0, ddp), 1)    # то, что город рисует ближе дальности: закрывает дальние дороги
        Tvis = Tfar & ~Occ
        prec = (M & dilate(Tall, 2)).sum() / max(1, M.sum())
        cov = (Tvis & dilate(M, 2)).sum() / max(1, Tvis.sum())
        changed = (np.abs(B - C).sum(2) > 24).sum()
        res.append(dict(view=i, m_a=int(M.sum()), m_c=int(Mc.sum()), prec=float(prec), cov=float(cov), changed=int(changed), truth=int(Tvis.sum()), dd=ddp, eye=eye.tolist(), fwd=fwd.tolist()))
    return res

def read_blocks(path):
    """RD35 -> [(рамка minx,miny,minz,maxx,maxy,maxz, число треугольников)] (для модели отбора движка)"""
    b = Path(path).read_bytes(); assert b[:4] == b'RD35', 'не RD35'
    nb = struct.unpack_from('<I', b, 4)[0]; out = []
    for i in range(nb):
        v = struct.unpack_from('<6f2I', b, 32 + 32 * i); out.append((v[:6], v[7] // 3))
    return out


CMG = 5.0   # RD_CMG движка: запас ящиков при отборе


def frame_tris(blocks, eye, yaw_deg, dd, fov=55.0, pitch=0.0, maxb=56):
    """модель отбора road934Draw (viewer/road934.h): те же выражения — круг по рамке блока в кольце [drawDist-30, 520] по плану и внутри 4 боковых плоскостей кадра (setupPlanes с запасом 1,03); -> (треугольников, блоков)"""
    a = math.radians(yaw_deg); f = np.array([math.sin(a) * math.cos(pitch), math.sin(pitch), -math.cos(a) * math.cos(pitch)])
    rx, rz = -f[2], f[0]; rl = math.hypot(rx, rz); rx, rz = rx / rl, rz / rl
    ux, uy, uz = -rz * f[1], rz * f[0] - rx * f[2], rx * f[1]
    tv = math.tan(math.radians(fov) * .5) * 1.03; th = tv * ASPECT
    pl = np.array([[f[0] * th - rx, f[1] * th, f[2] * th - rz], [f[0] * th + rx, f[1] * th, f[2] * th + rz],
                   [f[0] * tv - ux, f[1] * tv - uy, f[2] * tv - uz], [f[0] * tv + ux, f[1] * tv + uy, f[2] * tv + uz]])
    near_ = max(dd - 30.0, 60.0); sel = []
    for bb, nt in blocks:
        cx, cz = (bb[0] + bb[3]) * .5, (bb[2] + bb[5]) * .5; rad = math.hypot((bb[3] - bb[0]) * .5, (bb[5] - bb[2]) * .5)
        d = (cx - eye[0]) ** 2 + (cz - eye[2]) ** 2
        if d > (520.0 + CMG + rad) ** 2: continue
        t = near_ - CMG - rad
        if t > 0 and d < t * t: continue
        ok = True
        for i in range(2):   # слой режется боковыми плоскостями кадра (лево/право), как в движке
            px = (bb[3] + CMG if pl[i, 0] > 0 else bb[0] - CMG) - eye[0]; py = (bb[4] + CMG if pl[i, 1] > 0 else bb[1] - CMG) - eye[1]; pz = (bb[5] + CMG if pl[i, 2] > 0 else bb[2] - CMG) - eye[2]
            if px * pl[i, 0] + py * pl[i, 1] + pz * pl[i, 2] < 0: ok = False; break
        if ok: sel.append((d, nt))
    sel.sort(key=lambda t: t[0]); sel = sel[:maxb]
    return sum(t[1] for t in sel), len(sel)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('a'); ap.add_argument('b', nargs='?'); ap.add_argument('c', nargs='?')
    ap.add_argument('--names', default=''); ap.add_argument('--fov', type=float, default=55.0)
    ap.add_argument('--dmin', type=float, default=270.0); ap.add_argument('--dmax', type=float, default=500.0)
    ap.add_argument('--views', type=int, default=24); ap.add_argument('--red', action='store_true')
    ap.add_argument('--dds', type=lambda t: [float(x) for x in t.split(',')], default=[100.0, 130.0, 150.0, 200.0, 250.0]); ap.add_argument('--max-tris', type=int, default=3000); ap.add_argument('--cost-us', type=float, default=26.0); ap.add_argument('--fresh-us', type=float, default=30.0)
    ap.add_argument('--min-iou', type=float, default=0.90); ap.add_argument('--dd', type=float, default=0.0); ap.add_argument('--tol', type=int, default=1); ap.add_argument('--cov-min', type=float, default=0.30); ap.add_argument('--prec-min', type=float, default=0.90)
    a = ap.parse_args()
    nmp = names_path(a.names)
    if a.cmd == 'pick':
        Pq, isbr = truth(a.a, nmp)
        for e, a0, s in pick(Pq, isbr, int(a.b), a.fov, a.dmin, a.dmax):
            print('%.1f %.2f %.1f %d %.0f' % (e[0], e[1], e[2], a0, s))
    elif a.cmd == 'data':
        Pq, isbr = truth(a.a, nmp); Pr = read_rd34(a.b)
        if a.red:   # красный контроль: слой «как до правки» — дороги кончаются на 200 м (клин блоков по расстоянию)
            c = Pr.mean(1)
            # центр кадра неизвестен до выбора вида: обрезаем ниже по виду
        views = pick(Pq, isbr, a.views, a.fov, a.dmin, a.dmax)
        bad = 0; tot = []
        for e, a0, s in views:
            cam = camera(e, a0, a.fov)
            ma = raster(Pq, cam, a.dmin, a.dmax)
            mb = raster(Pr, cam, a.dmin, 200.0) if a.red else raster(Pr, cam, a.dmin, a.dmax)   # красный: слой «как до правки» кончается на 200 м — в кольцо 270–500 м не попадает ничего
            if a.tol:   # допуск a.tol px: край на растре видеочипа и так гуляет на ±0,5 px; охват и точность считаем относительно расширенных масок
                rec = (ma & dilate(mb, a.tol)).sum() / max(1, ma.sum()); pre = (mb & dilate(ma, a.tol)).sum() / max(1, mb.sum()); iou = min(rec, pre)
            else:
                u = (ma | mb).sum(); iou = (ma & mb).sum() / u if u else 1.0
            tot.append((iou, int(ma.sum()), int(mb.sum())))
            if iou < a.min_iou: bad += 1
        ious = [t[0] for t in tot]
        print('виды %d, IoU мин %.3f ср %.3f, ниже %.2f: %d, пикселей эталона ср %d, слоя ср %d' % (len(tot), min(ious), sum(ious) / len(ious), a.min_iou, bad, sum(t[1] for t in tot) // len(tot), sum(t[2] for t in tot) // len(tot)))
        sys.exit(1 if bad else 0)
    elif a.cmd == 'frametris':   # frametris LEVEL.shr ROAD934.shr [--dds 100,150,250] [--max-tris 3000] [--views N]: в кадре не больше N треугольников на любой позе (глаз на дороге +2,3 м, 24 курса, 3 дальности города)
        Pq, isbr = truth(a.a, nmp); blk = read_blocks(a.b); rng = np.random.default_rng(7)
        road = np.nonzero(isbr == 0)[0]; cen = Pq.mean(1)
        cand = rng.choice(road, min(a.views, len(road)), replace=False)
        worst = (0, None); allv = []
        for c in cand:
            e = cen[c] + np.array([0, 2.3, 0])
            for yaw in range(0, 360, 15):
                for dd in a.dds:
                    nt, nb = frame_tris(blk, e, yaw, dd)
                    allv.append(nt)
                    if nt > worst[0]: worst = (nt, (e.round(0).tolist(), yaw, dd, nb))
        allv = np.array(allv)
        print('поз %d, треугольников в кадре: макс %d (глаз %s, курс %d, город %d м, блоков %d), p99 %d, среднее %d, предел %d' % (len(allv), worst[0], worst[1][0], worst[1][1], worst[1][2], worst[1][3], int(np.percentile(allv, 99)), int(allv.mean()), a.max_tris))
        sys.exit(1 if worst[0] > a.max_tris else 0)
    elif a.cmd == 'cost':   # cost smoke.txt [--max-tris N] [--cost-us U] [--fresh-us F]: строки «ROAD934 cost» журнала движка; код 0 = в кадре не больше N треугольников, цена худшего вида (отбор переиспользуется, как в игре) не больше U, цена худшего кадра с отбором заново не больше F
        # окна одного вида (камера стоит) делают ту же работу — у них одинаковые (блоков, треугольников, дальность); шум загруженного Мака только прибавляет время,
        # поэтому цена вида = наименьшее avg_us среди его окон, цена худшего вида = наибольшая из этих цен. hit — число кадров окна с переиспользованным отбором: окно «заново» hit < 6, окно «с переиспользованием» hit >= 30, смешанные не считаем
        rows = []
        for ln in Path(a.a).read_text(errors='replace').splitlines():
            m = re.match(r'ROAD934 cost level=(\d+) avg_us=(\d+) max_us=(\d+) blocks=(\d+) tris=(\d+) calls=(\d+) drawDist=(\d+)(?: hit=(\d+))?', ln)
            if m and int(m.group(5)) > 0: rows.append([int(x) if x is not None else 0 for x in m.groups()])
        if not rows: print('нет строк ROAD934 cost с треугольниками'); sys.exit(1)
        def worst(sel):
            grp = {}
            for r in sel: grp.setdefault((r[3], r[4], r[6]), []).append(r[1])
            return (max(min(v) for v in grp.values()), len(grp)) if grp else (None, 0)
        fresh, nf = worst([r for r in rows if r[7] < 6]); cached, nc = worst([r for r in rows if r[7] >= 30]); mx = max(r[4] for r in rows)
        ok = mx <= a.max_tris and cached is not None and fresh is not None and cached <= a.cost_us and fresh <= a.fresh_us
        f = lambda v: 'нет окон' if v is None else '%d мкс (≈ %.3f мс PSP ×5,8)' % (v, v * 5.8 / 1000)
        print('окон %d; цена худшего вида с переиспользованием отбора (как в игре, видов %d): %s, предел %.0f мкс; худшего кадра с отбором заново (видов %d): %s, предел %.0f мкс; в кадре до %d треугольников (предел %d), блоков до %d' % (len(rows), nc, f(cached), a.cost_us, nf, f(fresh), a.fresh_us, mx, a.max_tris, max(r[3] for r in rows)))
        sys.exit(0 if ok else 1)
    elif a.cmd == 'scen':
        views = read_views(a.b); sys.stdout.write(scenario(int(a.a), views, a.fov))
    elif a.cmd == 'shots':
        views = read_views(a.c)
        dd = float(a.dd) if hasattr(a, 'dd') and a.dd else 150.0
        res = shots_metrics(a.a, a.b, views, nmp, a.fov, dd, 0, a.red)
        bad = 0; seen = 0
        for r in res:
            if r is None: print('нет кадров'); bad += 1; continue
            print('вид %d: пурпур %d (слоя нет: %d), точность %.2f, охват эталона %.2f, изменено пикселей %d, эталон %d, дальность города %.0f' % (r['view'], r['m_a'], r['m_c'], r['prec'], r['cov'], r['changed'], r['truth'], r['dd']))
            if r['m_c']: bad += 1; print('  кадр без слоя содержит пурпур')
            if r['truth'] >= 300:
                seen += 1
                if r['cov'] < a.cov_min: bad += 1; print('  охват %.2f < %.2f' % (r['cov'], a.cov_min))
            if r['m_a'] and r['prec'] < a.prec_min: bad += 1; print('  точность %.2f < %.2f' % (r['prec'], a.prec_min))
        if seen == 0: bad += 1; print('ни одного вида с эталоном >= 300 пикселей')
        sys.exit(1 if bad else 0)
    else:
        raise SystemExit('неизвестная команда')


if __name__ == '__main__':
    main()
