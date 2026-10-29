"""Экспорт уровня SHAR для PSP (формат SHR7): город клетками 40x40 м + небо + карта высот + машина.
python tools/psp_export.py            -> весь уровень 1
python tools/psp_export.py 2          -> уровень 2
python tools/psp_export.py --out /tmp/x.shr  -> записать в другой файл (по умолчанию build/level.shr)"""
import sys, json, struct, re
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from convert import Converter, GAME, OUT
from p3d import read

CAP, CHUNK, SPLIT, SPLIT_GROUND, CELL, LAYERS = 128, 40.0, 14.0, 7.0, 1.5, 4
SKY_S = 1 / 60   # небо ужимаем и рисуем вокруг камеры
SKY_NAMES = ('horizon', 'sky')
FAR_MIN = 1.2   # в дальней версии куска выкидываем исходные треугольники мельче этого (м²)
FAR_SPLIT = 28.0  # дальняя версия = исходные треугольники, лишь рёбра длиннее 28 м делим пополам. PSP выбрасывает
                  # треугольник целиком, если хоть одна вершина вне гвард-бэнда 4096 px (~83.7° от оси взгляда при
                  # вьюпорте 480x272, fovy 62°). От угла кадра до этой границы >= 33.7°, дальний кусок весь >= 50 м
                  # от глаза -> видимый треугольник с такой вершиной имеет ребро >= 2*50*sin(33.7°/2) = 29.0 м
PIECE_VERTS = 60000   # «суп» вершин (ближняя + дальняя версия) на кусок; уникальных всегда <= 65535
SKY_SECTORS = 8   # небо — 8 секторов по 45° (азимут центра треугольника вокруг камеры), движок отсекает их пирамидой
SKY_CAP = 30.0    # ...и «шапка» над головой (центр треугольника ближе 30 ужатых м к оси): иначе ящик каждого сектора
                  # дотягивается до оси, накрывает глаз и не отсекается никогда
GRAD_TOL = 0.5    # текстура неба = вертикальный градиент, если в каждой строке пиксели отличаются не больше чем на 0.5
BAKE_MAX = 8.0    # ...и вмешиваем её в цвет вершин, только если плавная заливка отличается от текстуры не больше 8/255
SPAWN = {1: ((220, 3.5, 172), np.pi / 2)}
VT = [('u', '<f4'), ('v', '<f4'), ('c', '<u4'), ('x', '<f4'), ('y', '<f4'), ('z', '<f4')]

def load_tex(url, cache, blob):
    if not url: return -1
    if url in cache: return cache[url]
    img = Image.open(OUT / url).convert('RGBA')
    w, h = img.size; s = min(1.0, CAP / max(w, h))
    w, h = max(16, int(w * s)), max(8, int(h * s))
    if img.size != (w, h): img = img.resize((w, h), Image.LANCZOS)
    q = img.quantize(256, method=Image.Quantize.FASTOCTREE)
    pal = np.zeros((256, 4), np.uint8)
    p = np.array(q.getpalette(rawmode='RGBA'), np.uint8).reshape(-1, 4)[:256]; pal[:len(p)] = p
    levels = []; lw, lh, cur = w, h, img
    while lw >= 16 and len(levels) < 8:
        if levels:
            a = np.asarray(cur, np.int32).reshape(-1, 4)
            idx = ((a[:, None, :] - pal[None].astype(np.int32)) ** 2).sum(2).argmin(1).astype(np.uint8)
        else: idx = np.asarray(q, np.uint8).reshape(-1)
        levels.append(idx.tobytes())
        lw, lh = lw // 2, max(1, lh // 2)
        if lw >= 16: cur = img.resize((lw, lh), Image.LANCZOS)
    out = struct.pack('<HHH10x', w, h, len(levels)) + pal.tobytes()
    for lv in levels: out += lv + b'\0' * (-len(lv) % 16)
    blob.append(out); cache[url] = len(blob) - 1
    return cache[url]

def subdivide_lod(P, UV, C, split=SPLIT, ground_split=SPLIT_GROUND, far_split=None):
    """Режем длинные треугольники: PSP не обрезает их у камеры, и дорога у машины пропадала бы.
    Делим самое длинное ребро пополам, пока оно длиннее split (земля/дорога — ground_split).
    far_split: заодно собираем дальнюю версию — те же исходные треугольники, порезанные только до far_split
    («дальние предки»). Каждый мелкий треугольник — потомок ровно одного предка, края совпадают.
    -> P, UV, C                                     (far_split=None)
    -> P, UV, C, anc, (fP, fUV, fC, forig)          anc: номер предка у каждого мелкого треугольника,
                                                    forig: номер исходного треугольника у каждого предка"""
    P, UV, C = P.reshape(-1, 3, 3), UV.reshape(-1, 3, 2), C.reshape(-1, 3)
    orig, anc = np.arange(len(P)), np.full(len(P), -1)
    done, far, nfar = [], [], 0
    def adopt(new):   # треугольники new становятся дальними предками
        nonlocal nfar
        if not new.any(): return
        anc[new] = nfar + np.arange(int(new.sum())); nfar += int(new.sum())
        far.append((P[new], UV[new], C[new], orig[new]))
    for _ in range(10):
        e = np.stack([np.linalg.norm(P[:, (i + 1) % 3] - P[:, i], axis=1) for i in range(3)], 1)
        if far_split is not None: adopt((anc < 0) & (e.max(1) <= far_split))
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); ln = np.linalg.norm(nrm, axis=1) + 1e-9
        flat = np.abs(nrm[:, 1]) / ln > 0.55   # дорога/земля: режем мельче, чтобы не пропадала у камеры
        big = e.max(1) > np.where(flat, ground_split, split)
        if far_split is not None: adopt((anc < 0) & ~big)   # страховка: готовый треугольник без предка (NaN-вершины) сам себе предок, иначе anc = -1
        done.append((P[~big], UV[~big], C[~big], anc[~big]))
        if not big.any(): P = P[:0]; break
        P, UV, C, k, orig, anc = P[big], UV[big], C[big], e[big].argmax(1), orig[big], anc[big]
        n = np.arange(len(P)); i0, i1, i2 = k, (k + 1) % 3, (k + 2) % 3
        def mid(A): return (A[n, i0] + A[n, i1]) / 2
        mp, mu = mid(P), mid(UV)
        c0, c1 = C[n, i0], C[n, i1]
        mc = ((((c0 & 0xFF) + (c1 & 0xFF)) // 2) | ((((c0 >> 8) & 0xFF) + ((c1 >> 8) & 0xFF)) // 2 << 8) |
              ((((c0 >> 16) & 0xFF) + ((c1 >> 16) & 0xFF)) // 2 << 16) | (0xFF << 24)).astype(np.uint32)
        a = np.stack([P[n, i0], mp, P[n, i2]], 1); b = np.stack([mp, P[n, i1], P[n, i2]], 1)
        ua = np.stack([UV[n, i0], mu, UV[n, i2]], 1); ub = np.stack([mu, UV[n, i1], UV[n, i2]], 1)
        ca = np.stack([c0, mc, C[n, i2]], 1); cb = np.stack([mc, c1, C[n, i2]], 1)
        P, UV, C = np.concatenate([a, b]), np.concatenate([ua, ub]), np.concatenate([ca, cb])
        orig, anc = np.concatenate([orig, orig]), np.concatenate([anc, anc])
    if len(P):
        if far_split is not None: adopt(anc < 0)
        done.append((P, UV, C, anc))
    out = (np.concatenate([d[0] for d in done]).reshape(-1, 3), np.concatenate([d[1] for d in done]).reshape(-1, 2),
           np.concatenate([d[2] for d in done]).reshape(-1))
    if far_split is None: return out
    if not far:   # пустой примитив (0 треугольников): np.concatenate([]) упал бы
        far = [(np.zeros((0, 3, 3), np.float32), np.zeros((0, 3, 2), np.float32), np.zeros((0, 3), np.uint32), np.zeros(0, int))]
    fP, fUV, fC, forig = (np.concatenate([f[i] for f in far]) for i in range(4))
    return out + (np.concatenate([d[3] for d in done]), (fP.reshape(-1, 3), fUV.reshape(-1, 2), fC.reshape(-1), forig))

def subdivide(P, UV, C, split=SPLIT, ground_split=SPLIT_GROUND):
    return subdivide_lod(P, UV, C, split, ground_split)

def tri_area(P):
    T = np.asarray(P, np.float64).reshape(-1, 3, 3)
    return np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2

def gradient_rows(url):
    """Текстура — чистый вертикальный градиент (каждая строка одного цвета)? -> цвета строк (H, 4) или None"""
    a = np.asarray(Image.open(OUT / url).convert('RGBA'), np.float64)
    return a.mean(1) if np.abs(a - a.mean(1, keepdims=True)).max() <= GRAD_TOL else None

def sample_rows(rows, v):
    """Цвет градиента в точке v так, как его берёт PSP: билинейно по v, повтор текстуры (GU_REPEAT)."""
    H = len(rows); y = np.asarray(v, np.float64) * H - .5; i0 = np.floor(y).astype(int); f = (y - i0)[..., None]
    return rows[i0 % H] * (1 - f) + rows[(i0 + 1) % H] * f

def abgr_split(C): return np.stack([(C >> s) & 0xFF for s in (0, 8, 16, 24)], -1).astype(np.float64)   # -> r, g, b, a

def bake_gradient(UV, C, rows, n=12):
    """Цвет градиентной текстуры в каждой вершине вмешиваем в цвет вершины (как GU_TFX_MODULATE).
    -> новые цвета и макс. ошибка (0..255) внутри треугольников против текстуры (выборка n*(n+1)/2 точек)."""
    vq = np.round(UV[:, 1] * 256) / 256                                # v так, как оно ляжет в файл
    col = abgr_split(C); tex = sample_rows(rows, vq)
    baked = np.clip(np.round(tex * col / 255), 0, 255).astype(np.uint32)
    newC = (baked[:, 0] | baked[:, 1] << 8 | baked[:, 2] << 16 | baked[:, 3] << 24).astype(np.uint32)
    i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1)); m = i + j <= n
    w = np.stack([i[m], j[m], n - i[m] - j[m]], 1) / n                 # барицентрические точки
    V, CO, BK = vq.reshape(-1, 3), col.reshape(-1, 3, 4), baked.reshape(-1, 3, 4).astype(np.float64)
    truth = sample_rows(rows, V @ w.T) * np.einsum('pk,tkc->tpc', w, CO) / 255   # текстура * цвет вершины
    gour = np.einsum('pk,tkc->tpc', w, BK)                                        # плавная заливка вершин
    return newC, float(np.abs(truth - gour).max(initial=0.0))

def is_sky(obj): return obj['name'].lower().startswith(SKY_NAMES)
JUNK_MESHES = ('Plane1Shape',)   # служебная плоскость с палитрой в небе

def pack_prims(meta, raw, conv_cache, blob, want=lambda o: True):
    """-> список (tex, flags, P, UV, C) в координатах объекта*матрица"""
    out = []
    for obj in meta['objects']:
        if not want(obj) or obj['mesh'] in JUNK_MESHES: continue
        M = np.array(obj['matrix'], np.float64).reshape(4, 4)
        for prim in meta['meshes'].get(obj['mesh'], []):
            at = prim['attributes']
            g = lambda k, w, t='<f4': np.frombuffer(raw, t, at[k][1], at[k][0]).reshape(-1, w) if w > 1 else np.frombuffer(raw, t, at[k][1], at[k][0])
            pos, uv, col, idx = g('position', 3), g('uv', 2), g('color', 3), g('indices', 1, '<u4')
            world = (np.c_[pos, np.ones(len(pos))] @ M)[:, :3]
            mat = meta['materials'].get(prim['shader'], {})
            t = load_tex(mat.get('textureUrl', ''), conv_cache, blob)
            flags = (1 if mat.get('alpha') else 0) | (2 if mat.get('translucent') or mat.get('blend') else 0)
            c = np.clip(col * 255, 0, 255).astype(np.uint32)
            abgr = (0xFF << 24) | (c[:, 2] << 16) | (c[:, 1] << 8) | c[:, 0]
            out.append((t, flags, world[idx].astype(np.float32), uv[idx].astype(np.float32), abgr[idx].astype(np.uint32)))
    return out

def verts(P, UV, C):
    v = np.zeros(len(P), dtype=VT)
    v['u'], v['v'], v['c'] = UV[:, 0], UV[:, 1], C
    v['x'], v['y'], v['z'] = P[:, 0], P[:, 1], P[:, 2]
    return v

def heightmap(tris):
    lo = tris.reshape(-1, 3).min(0); hi = tris.reshape(-1, 3).max(0)
    W, H = int((hi[0] - lo[0]) / CELL) + 2, int((hi[2] - lo[2]) / CELL) + 2
    hm = np.full((H, W, LAYERS), -32768, np.int16)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1); ok = ln > 1e-6
    tris, n = tris[ok], n[ok] / ln[ok, None]
    walk = np.abs(n[:, 1]) > 0.55
    for t in tris[walk]:
        x0, x1 = int((t[:, 0].min() - lo[0]) / CELL), int((t[:, 0].max() - lo[0]) / CELL)
        z0, z1 = int((t[:, 2].min() - lo[2]) / CELL), int((t[:, 2].max() - lo[2]) / CELL)
        xs, zs = np.meshgrid(np.arange(x0, x1 + 1), np.arange(z0, z1 + 1))
        px, pz = lo[0] + (xs + .5) * CELL, lo[2] + (zs + .5) * CELL
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(d) < 1e-9: continue
        w1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / d
        w2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / d
        w3 = 1 - w1 - w2
        inside = (w1 >= -.05) & (w2 >= -.05) & (w3 >= -.05)
        if not inside.any(): continue
        hy = (w1 * ay + w2 * by + w3 * cy)[inside]
        for zz, xx, yy in zip(zs[inside], xs[inside], hy):
            cm = int(np.clip(yy * 100, -32000, 32000)); cell = hm[zz, xx]
            if (np.abs(cell.astype(np.int32) - cm) < 40).any(): continue
            free = np.where(cell == -32768)[0]
            if len(free): cell[free[0]] = cm
            else:
                j = cell.argmin()
                if cm > cell[j]: cell[j] = cm
    # стены: крутые треугольники коллизии -> по клетке диапазон высот, который нельзя проехать
    wall = np.zeros((H, W, 2), np.int16); wall[..., 0] = 32767; wall[..., 1] = -32767
    steep = tris[~walk]
    for t in steep:
        e = max(np.linalg.norm(t[1] - t[0]), np.linalg.norm(t[2] - t[1]), np.linalg.norm(t[0] - t[2]))
        n = int(min(80, max(1, e / (CELL * .5))))
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1)); m = i + j <= n
        a, b = i[m] / n, j[m] / n; pts = t[0] + a[:, None] * (t[1] - t[0]) + b[:, None] * (t[2] - t[0])
        gx = ((pts[:, 0] - lo[0]) / CELL).astype(int); gz = ((pts[:, 2] - lo[2]) / CELL).astype(int)
        ok2 = (gx >= 0) & (gz >= 0) & (gx < W) & (gz < H)
        gx, gz, yy = gx[ok2], gz[ok2], np.clip(pts[ok2, 1] * 100, -32000, 32000).astype(np.int16)
        np.minimum.at(wall[..., 0], (gz, gx), yy); np.maximum.at(wall[..., 1], (gz, gx), yy)
    return lo, W, H, hm, wall

def main(level, out_path=None):
    art = GAME / 'art'
    scenes = [f'l{level}_terra'] + sorted(p.stem for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
    conv = Converter(); blob = []; cache = {}
    for path in sorted(art.glob(f'l{level}*.p3d')):
        try: conv.resources(read(path))
        except Exception as e: print('skip', path.name, e)
    groups, coll, sky = {}, [], []
    for scene in scenes:
        conv.export(art / f'{scene}.p3d', f'psp_{scene}')
        meta = json.loads((OUT / f'psp_{scene}.json').read_text()); raw = (OUT / f'psp_{scene}.bin').read_bytes()
        for t, fl, P, UV, C in pack_prims(meta, raw, cache, blob, is_sky):
            sky.append((t, fl, P, UV, C))
        for t, fl, P, UV, C in pack_prims(meta, raw, cache, blob, lambda o: not is_sky(o)):
            oarea = tri_area(P)
            P, UV, C, anc, (fP, fUV, fC, forig) = subdivide_lod(P, UV, C, far_split=FAR_SPLIT)
            # клетку выбирает дальний предок (по своему центру), мелкие потомки идут за ним в тот же кусок:
            # иначе ближняя и дальняя версии одной поверхности разъехались бы по разным кускам (дыры/двойники)
            keys = np.floor(fP.reshape(-1, 3, 3).mean(1)[:, [0, 2]] / CHUNK).astype(int)
            keep = oarea[forig] >= FAR_MIN
            for key in {tuple(k) for k in keys}:
                fm = (keys == key).all(1); nm = fm[anc]
                local = np.cumsum(fm) - 1
                groups.setdefault((key, t, fl), []).append(
                    (verts(P[np.repeat(nm, 3)], UV[np.repeat(nm, 3)], C[np.repeat(nm, 3)]), local[anc[nm]],
                     verts(fP[np.repeat(fm, 3)], fUV[np.repeat(fm, 3)], fC[np.repeat(fm, 3)]), keep[fm]))
        if meta.get('collision'):
            o, n = meta['collision']; coll.append(np.frombuffer(raw, '<f4', n, o).reshape(-1, 3, 3))
        for ext in ('json', 'bin'): (OUT / f'psp_{scene}.{ext}').unlink()
    print('карта высот…', flush=True)
    tris = np.concatenate(coll); lo, W, H, hm, wall = heightmap(tris)

    # машина семьи Симпсонов
    car_groups = {}
    carp = art / 'cars' / 'famil_v.p3d'
    lift = 0.0
    if carp.exists():
        conv.export(carp, 'psp_car', vehicle=True)
        meta = json.loads((OUT / 'psp_car.json').read_text()); raw = (OUT / 'psp_car.bin').read_bytes()
        for t, fl, P, UV, C in pack_prims(meta, raw, cache, blob):
            v = verts(P, UV, C)   # машину не режем: дальняя версия = она же без мелочи (движок её не берёт)
            car_groups.setdefault(((0, 0), t, fl), []).append((v, np.arange(len(v) // 3), v, tri_area(P) >= FAR_MIN))
        ally = np.concatenate([p[0]['y'] for v in car_groups.values() for p in v])
        lift = -float(ally.min())
        for ext in ('json', 'bin'): (OUT / f'psp_car.{ext}').unlink()

    # небо: вокруг центра, ужатое, режем крупно (в ужатых метрах); 8 секторов по азимуту, чтобы движок
    # не рисовал то, что за кадром. Градиентные текстуры (l1_backfade*) вмешиваем в цвет вершин, без текстуры.
    sky_groups = {}
    if sky:
        urls = {i: u for u, i in cache.items()}; grads, baked = {}, []
        allp = np.concatenate([P for _, _, P, _, _ in sky]); sc = (allp.min(0) + allp.max(0)) / 2; sc[1] = 0
        for t, fl, P, UV, C in sky:
            P, UV, C = subdivide((P - sc) * SKY_S, UV, C, SPLIT, SPLIT)
            if t >= 0 and t not in grads: grads[t] = gradient_rows(urls[t])
            if t >= 0 and grads[t] is not None:
                C2, err = bake_gradient(UV, C, grads[t]); baked.append((urls[t], len(P) // 3, err))
                if err <= BAKE_MAX:   # без текстуры; UV обнуляем, чтобы вершины лучше склеились
                    C, t, UV = C2, -1, np.zeros_like(UV)
            cen = P.reshape(-1, 3, 3).mean(1)
            sec = np.floor((np.arctan2(cen[:, 0], cen[:, 2]) + np.pi) / (2 * np.pi / SKY_SECTORS)).astype(int) % SKY_SECTORS
            sec[np.hypot(cen[:, 0], cen[:, 2]) < SKY_CAP] = SKY_SECTORS                  # шапка
            for s_ in np.unique(sec):
                sel = np.repeat(sec == s_, 3); v = verts(P[sel], UV[sel], C[sel]); n = len(v) // 3
                sky_groups.setdefault(((int(s_), 0), t, fl | 4), []).append((v, np.arange(n), v, np.ones(n, bool)))
        print(f'небо: {sum(len(p[0]) for v in sky_groups.values() for p in v) // 3} треугольников, '
              f'{len(sky_groups)} кусков ({SKY_SECTORS} секторов + шапка)')
        for u, n, err in baked:
            print(f'  градиент {u} ({n} треуг.): макс. ошибка заливки {err:.2f}/255 -> '
                  + ('цвет вершин, без текстуры' if err <= BAKE_MAX else 'оставляем текстуру'))

    allv = np.concatenate([p[0] for v in groups.values() for p in v])
    bb = [allv['x'].min(), allv['y'].min(), allv['z'].min(), allv['x'].max(), allv['y'].max(), allv['z'].max()]
    (sx, sy, sz), sh = SPAWN.get(level, (((bb[0] + bb[3]) / 2, bb[4], (bb[2] + bb[5]) / 2), 0.0))
    # клетки: всё, что в клетке, лежит одним блоком и грузится за одно чтение
    cellkeys = sorted({k[0] for k in groups})
    owners = [(0, [k for k in groups if k[0] == ck]) for ck in cellkeys]
    owners += [(1, list(car_groups)), (2, list(sky_groups))]
    src = {0: groups, 1: car_groups, 2: sky_groups}
    QV = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('pad', '<i2')])
    # текстуры, которые никто не использует (градиенты неба ушли в цвет вершин), не кладём в файл
    used = sorted({k[1] for d in src.values() for k in d if k[1] >= 0})
    tmap = {t: i for i, t in enumerate(used)}; blob = [blob[t] for t in used]
    cells, pieces, tris_total, far_total = [], [], 0, 0
    for owner, keys in owners:
        if not keys: continue
        first, cblob, clo, chi = len(pieces), bytearray(), np.full(3, 1e9), np.full(3, -1e9)
        for key in sorted(keys, key=lambda k: (k[2], k[1])):
            parts = src[owner][key]   # (ближний суп, № предка у каждого ближнего треуг., дальний суп, дальний нужен?)
            nv = np.concatenate([p[0] for p in parts]); fv = np.concatenate([p[2] for p in parts])
            base = np.cumsum([0] + [len(p[3]) for p in parts])[:-1]
            anc = np.concatenate([p[1] + b for p, b in zip(parts, base)]); keep = np.concatenate([p[3] for p in parts])
            if owner == 0: tris_total += len(nv) // 3; far_total += int(keep.sum())
            # режем на куски по ~PIECE_VERTS вершин супа (ближняя + дальняя версии); предок и его потомки не разлучаются
            w = np.bincount(anc, minlength=len(keep)) * 3 + keep * 3
            chunk = (np.cumsum(w) - w) // PIECE_VERTS
            for ch in range(int(chunk.max()) + 1):
                nm, fm = chunk[anc] == ch, (chunk == ch) & keep
                vn, vf = nv[np.repeat(nm, 3)], fv[np.repeat(fm, 3)]
                if not len(vn): continue
                vv = np.concatenate([vn, vf])   # обе версии — один массив вершин (почти все вершины общие)
                P = np.stack([vv['x'], vv['y'], vv['z']], 1).astype(np.float64)
                lo_, hi_ = P.min(0), P.max(0); c = (lo_ + hi_) / 2; S = max(float((hi_ - lo_).max()) / 2, 1e-3)
                clo, chi = np.minimum(clo, lo_), np.maximum(chi, hi_)
                q = np.zeros(len(vv), QV)
                q['x'], q['y'], q['z'] = [np.clip(np.round((P[:, j] - c[j]) / S * 32767), -32767, 32767) for j in range(3)]
                q['u'] = np.clip(np.round(vv['u'] * 256), -32767, 32767); q['v'] = np.clip(np.round(vv['v'] * 256), -32767, 32767)
                q['c'] = vv['c']
                uniq, inv = np.unique(q, return_inverse=True); inv = inv.reshape(-1)
                assert len(uniq) <= 65535, (key, len(uniq))
                near, far = inv[:len(vn)], inv[len(vn):]
                off = len(cblob)
                cblob += uniq.tobytes(); cblob += b'\0' * (-len(cblob) % 16)
                cblob += near.astype('<u2').tobytes(); cblob += b'\0' * (-len(cblob) % 16)
                cblob += far.astype('<u2').tobytes(); cblob += b'\0' * (-len(cblob) % 16)
                pieces.append((lo_, hi_, tmap.get(key[1], -1), key[2], len(uniq), len(near), owner, c, S * 32768 / 32767, off, len(far), len(cells)))
        cells.append([clo, chi, first, len(pieces) - first, owner, bytes(cblob)])
    head = bytearray(b'SHR7' + struct.pack('<II', len(blob), len(pieces)))
    head += struct.pack('<6f4f f', *bb, sx, sy, sz, sh, lift)
    head += struct.pack('<3fII', lo[0], lo[2], CELL, W, H)
    head += b'\0' * 4                                   # 76: смещение таблицы кусков
    head += struct.pack('<II', len(cells), 0) + b'\0' * 8  # 80: клеток, 84: смещение таблицы клеток
    head += hm.tobytes(); head += b'\0' * (-len(head) % 16)
    head += wall.tobytes(); head += b'\0' * (-len(head) % 16)
    for t in blob: head += t; head += b'\0' * (-len(head) % 16)
    struct.pack_into('<I', head, 76, len(head))
    recs = bytearray()
    for lo_, hi_, t, fl, nv, ni, owner, c, S, off, nf, ci in pieces:
        recs += struct.pack('<6fiIIII3ffIII8x', *lo_, *hi_, t, fl, nv, ni, owner, *c, S, off, nf, ci)
    struct.pack_into('<I', head, 84, len(head) + len(recs))
    off = len(head) + len(recs) + 48 * len(cells); off += -off % 16; crecs = bytearray()
    for clo, chi, first, n, owner, cb in cells:
        crecs += struct.pack('<6fIIIII4x', *clo, *chi, first, n, owner, off, len(cb)); off += len(cb)
    out = head + recs + crecs; out += b'\0' * (-len(out) % 16); out += b''.join(c[5] for c in cells)
    dst = Path(out_path) if out_path else ROOT / 'build' / 'level.shr'
    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(out)
    mb = len(out) / 2**20
    print(f'{dst.name}: {mb:.1f} MB, {tris_total:,} треугольников (дальних {far_total:,}), {len(blob)} текстур, {len(cells)} клеток, {len(pieces)} кусков, карта {W}x{H}')

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='SHAR -> PSP level export (SHR7)')
    ap.add_argument('level', nargs='?', type=int, default=1)
    ap.add_argument('--out', default=str(ROOT / 'build' / 'level.shr'), help='куда писать (по умолчанию build/level.shr)')
    a = ap.parse_args()
    main(a.level, a.out)
