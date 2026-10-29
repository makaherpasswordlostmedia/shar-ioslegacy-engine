"""Экспорт уровня SHAR для PSP (формат SHR6): весь город кусками + карта высот + машина.
python tools/psp_export.py            -> весь уровень 1
python tools/psp_export.py 2          -> уровень 2"""
import sys, json, struct, re
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from convert import Converter, GAME, OUT
from p3d import read

CAP, CHUNK, SPLIT, CELL, LAYERS = 128, 40.0, 14.0, 1.5, 4
FAR_MIN = 1.2   # в дальней версии куска выкидываем треугольники мельче этого (м²)
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

def subdivide(P, UV, C):
    """Режем длинные треугольники: PSP не обрезает их у камеры, и дорога у машины пропадала бы."""
    P, UV, C = P.reshape(-1, 3, 3), UV.reshape(-1, 3, 2), C.reshape(-1, 3)
    done_p, done_uv, done_c = [], [], []
    for _ in range(8):
        e = np.stack([np.linalg.norm(P[:, (i + 1) % 3] - P[:, i], axis=1) for i in range(3)], 1)
        big = e.max(1) > SPLIT
        done_p.append(P[~big]); done_uv.append(UV[~big]); done_c.append(C[~big])
        if not big.any(): P = P[:0]; break
        P, UV, C, k = P[big], UV[big], C[big], e[big].argmax(1)
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
    if len(P): done_p.append(P); done_uv.append(UV); done_c.append(C)
    return np.concatenate(done_p).reshape(-1, 3), np.concatenate(done_uv).reshape(-1, 2), np.concatenate(done_c).reshape(-1)

def pack_prims(meta, raw, conv_cache, blob, M_override=None):
    """-> список (tex, flags, P, UV, C) в координатах объекта*матрица"""
    out = []
    for obj in meta['objects']:
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

def main(level):
    art = GAME / 'art'
    scenes = [f'l{level}_terra'] + sorted(p.stem for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
    conv = Converter(); blob = []; cache = {}
    for path in sorted(art.glob(f'l{level}*.p3d')):
        try: conv.resources(read(path))
        except Exception as e: print('skip', path.name, e)
    groups, coll = {}, []
    for scene in scenes:
        conv.export(art / f'{scene}.p3d', f'psp_{scene}')
        meta = json.loads((OUT / f'psp_{scene}.json').read_text()); raw = (OUT / f'psp_{scene}.bin').read_bytes()
        for t, fl, P, UV, C in pack_prims(meta, raw, cache, blob):
            P, UV, C = subdivide(P, UV, C)
            cen = P.reshape(-1, 3, 3).mean(1)
            keys = np.floor(cen[:, [0, 2]] / CHUNK).astype(int)
            for key in {tuple(k) for k in keys}:
                m = (keys == key).all(1); sel = np.repeat(m, 3)
                groups.setdefault((key, t, fl), []).append(verts(P[sel], UV[sel], C[sel]))
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
            car_groups.setdefault(((0, 0), t, fl), []).append(verts(P, UV, C))
        ally = np.concatenate([np.concatenate(v)['y'] for v in car_groups.values()])
        lift = -float(ally.min())
        for ext in ('json', 'bin'): (OUT / f'psp_car.{ext}').unlink()

    allv = np.concatenate([np.concatenate(v) for v in groups.values()])
    bb = [allv['x'].min(), allv['y'].min(), allv['z'].min(), allv['x'].max(), allv['y'].max(), allv['z'].max()]
    (sx, sy, sz), sh = SPAWN.get(level, (((bb[0] + bb[3]) / 2, bb[4], (bb[2] + bb[5]) / 2), 0.0))
    chunks = [(k, 0) for k in sorted(groups, key=lambda k: (k[2], k[1]))] + [(k, 1) for k in sorted(car_groups, key=lambda k: k[2])]
    # --- куски: каждый хранится отдельно и подгружается PSP по мере приближения ---
    QV = np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('pad', '<i2')])
    pieces, tris_total = [], 0
    for key, owner in chunks:
        v = np.concatenate((car_groups if owner else groups)[key]); tris_total += len(v) // 3
        for i in range(0, len(v), 60000): pieces.append((v[i:i + 60000], key, owner))
    table, blobs = [], []
    for v, key, owner in pieces:
        P = np.stack([v['x'], v['y'], v['z']], 1).astype(np.float64)
        lo_, hi_ = P.min(0), P.max(0); c = (lo_ + hi_) / 2; S = max(float((hi_ - lo_).max()) / 2, 1e-3)
        q = np.zeros(len(v), QV)
        q['x'], q['y'], q['z'] = [np.clip(np.round((P[:, i] - c[i]) / S * 32767), -32767, 32767) for i in range(3)]
        q['u'] = np.clip(np.round(v['u'] * 256), -32767, 32767); q['v'] = np.clip(np.round(v['v'] * 256), -32767, 32767)
        q['c'] = v['c']
        uniq, inv = np.unique(q, return_inverse=True); inv = inv.reshape(-1)
        T = P.reshape(-1, 3, 3); area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
        far = inv.reshape(-1, 3)[area >= FAR_MIN].reshape(-1)
        b = bytearray(uniq.tobytes()); b += b'\0' * (-len(b) % 16)
        b += inv.astype('<u2').tobytes(); b += b'\0' * (-len(b) % 16)
        b += far.astype('<u2').tobytes(); b += b'\0' * (-len(b) % 16)
        table.append((lo_, hi_, key[1], key[2], len(uniq), len(inv), owner, c, S * 32768 / 32767, len(far))); blobs.append(bytes(b))
    head = bytearray(b'SHR6' + struct.pack('<II', len(blob), len(pieces)))
    head += struct.pack('<6f4f f', *bb, sx, sy, sz, sh, lift)
    head += struct.pack('<3fII', lo[0], lo[2], CELL, W, H)
    head += b'\0' * 4  # смещение таблицы, заполним ниже
    head += hm.tobytes(); head += b'\0' * (-len(head) % 16)
    head += wall.tobytes(); head += b'\0' * (-len(head) % 16)
    for t in blob: head += t; head += b'\0' * (-len(head) % 16)
    struct.pack_into('<I', head, 76, len(head))
    data_off = len(head) + 80 * len(table); off = data_off; recs = bytearray()
    for (lo_, hi_, t, fl, nv, ni, owner, c, S, nf), b in zip(table, blobs):
        recs += struct.pack('<6fiIIII3ffII12x', *lo_, *hi_, t, fl, nv, ni, owner, *c, S, off, nf); off += len(b)
    out = head + recs + b''.join(blobs)
    dst = ROOT / 'build'; dst.mkdir(exist_ok=True); (dst / 'level.shr').write_bytes(out)
    mb = len(out) / 2**20
    print(f'level.shr: {mb:.1f} MB, {tris_total:,} треугольников, {len(blob)} текстур, {len(pieces)} кусков (подгружаются по мере езды), карта {W}x{H}')

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1)
