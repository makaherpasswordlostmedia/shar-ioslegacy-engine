"""Проверка PVS-секции в level.shr (её пишет tools/pvs.c).
python tools/pvs_check.py [LEVEL.shr] [--eyes 300] [--res 512] [--seed 1] [--no-exact]

[1] разбирает секцию PVS1 (смещение в заголовке @88), проверяет сортировку и что в списках только город;
[2] повторяет отсечение движка (cullPiece в viewer/main.c): ящик куска против 4 боковых плоскостей пирамиды
    (62° по вертикали x1.03, 16:9), дальность 115 м и LOD 50 м по расстоянию до ящика; строка «конус» = coneOut v7
    (сфера, дальность и LOD по сфере). В точках тест-прогона движка (169 точек x 4 направления, камера 7.5 м сзади и
    3.2 м вверх, смотрит на машину +1.4 м): вызовы/треугольники на кадр без PVS и с PVS (медиана/p90/макс).
    Строка «идеал» = точная видимость из этой самой точки (нижняя граница для любого PVS);
[3] консервативность: случайные глаза внутри клеток PVS на случайной допустимой высоте (слой карты высот
    + 1.2..6.5 м), точная видимость кубической картой RESxRES на грань (tools/pvs --exact), сколько видимых
    кусков нет в списке клетки: по числу, по пикселям, по пикселям с учётом тумана (60..115 м), по дальности."""
import sys, struct, argparse, subprocess, tempfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
NODATA = 0xFFFFFFFF
REC = np.dtype([('bb', '<f4', 6), ('tex', '<i4'), ('flags', '<u4'), ('nv', '<u4'), ('ni', '<u4'), ('owner', '<u4'),
                ('o', '<f4', 3), ('sc', '<f4'), ('off', '<u4'), ('nf', '<u4'), ('cell', '<u4'), ('pad', '<u4', 2)])
DRAW, LOD, NEAR, FOVY, ASPECT, FOG0 = 115., 50., 0.7, 62., 16 / 9, 60.
PVS_BIN = ROOT / 'tools' / 'pvs'
LRAD = 6.0

def fogw(d): return np.clip((DRAW - d) / (DRAW - FOG0), 0, 1)

def load(path):
    d = Path(path).read_bytes()
    assert d[:4] == b'SHR7', 'not SHR7'
    ntex, npc = struct.unpack_from('<II', d, 4)
    hd = struct.unpack_from('<14f', d, 12)
    W, H = struct.unpack_from('<II', d, 68)
    toff, ncell, coff, poff = struct.unpack_from('<IIII', d, 76)
    L = dict(hd=hd, W=W, H=H, hox=hd[11], hoz=hd[12], hcell=hd[13], sph=hd[9],
             hm=np.frombuffer(d, '<i2', W * H * 4, 104).reshape(H, W, 4),   # заголовок SHR7 104 Б (@96 propOff, @100 carOff)
             rec=np.frombuffer(d, REC, npc, toff), pvs=None)
    if poff:
        assert poff % 16 == 0 and d[poff:poff + 4] == b'PVS1', 'bad PVS offset/magic'
        ox, oz, cell = struct.unpack_from('<3f', d, poff + 4)
        gw, gh, pc, pad = struct.unpack_from('<4I', d, poff + 16)
        ent = np.frombuffer(d, '<u4', gw * gh * 2, poff + 32).reshape(gh * gw, 2)
        assert poff + 32 + 8 * gw * gh + 2 * pc <= len(d), 'PVS section truncated'
        pool = np.frombuffer(d, '<u2', pc, poff + 32 + 8 * gw * gh)
        lists = [None if c == NODATA else pool[s:s + c] for s, c in ent]
        for i, l in enumerate(lists):
            if l is None: continue
            assert int(ent[i, 0]) + len(l) <= pc, f'cell {i}: list out of pool'
            if len(l) > 1: assert (np.diff(l.astype(np.int64)) > 0).all(), f'cell {i}: list not sorted'
            if len(l): assert l.max() < npc and (L['rec']['owner'][l] == 0).all(), f'cell {i}: non-city piece'
        L['pvs'] = dict(off=poff, ox=ox, oz=oz, cell=cell, W=gw, H=gh, lists=lists, pool=pc, range=pad)
    return L

def dilate(P):
    W, H, lists = P['W'], P['H'], P['lists']; out = []
    for gz in range(H):
        for gx in range(W):
            if lists[gz * W + gx] is None: out.append(None); continue
            parts = [lists[z * W + x] for z in range(gz - 1, gz + 2) for x in range(gx - 1, gx + 2)
                     if 0 <= x < W and 0 <= z < H and lists[z * W + x] is not None]
            out.append(np.unique(np.concatenate(parts)))
    return dict(P, lists=out)

def cell_list(P, x, z):
    gx, gz = int(np.floor((x - P['ox']) / P['cell'])), int(np.floor((z - P['oz']) / P['cell']))
    if gx < 0 or gz < 0 or gx >= P['W'] or gz >= P['H']: return None
    return P['lists'][gz * P['W'] + gx]

def run_exact(path, eyes, res):
    with tempfile.TemporaryDirectory() as td:
        ef = Path(td) / 'eyes.txt'; ef.write_text(''.join(f'{x:.3f} {y:.3f} {z:.3f}\n' for x, y, z in eyes))
        out = subprocess.run([str(PVS_BIN), str(path), '--exact', str(ef), '--res', str(res)] + (['--range', str(int(DRAW))] if DRAW != 115. else []),
                             capture_output=True, text=True, check=True)
    return np.array([list(map(int, l.split())) for l in out.stdout.split('\n') if l.strip()], np.int64).reshape(-1, 3)

def bench_views(L):
    """точки как benchPoints() в viewer/main.c, 4 направления, камера как в тест-прогоне"""
    hm, W, H, hc = L['hm'], L['W'], L['H'], L['hcell']; st = int(50. / hc); views = []
    gz, row, npts = st // 2, 0, 0
    while gz < H:
        for j in range(W // st + 1):
            gx = st // 2 + ((W // st - j) if row & 1 else j) * st
            if gx < 0 or gx >= W: continue
            c = hm[gz, gx]; c = c[c != -32768]
            if not len(c) or npts >= 1024: continue
            x, y, z = L['hox'] + (gx + .5) * hc, c.min() * .01, L['hoz'] + (gz + .5) * hc; npts += 1
            for k in range(4):
                h = L['sph'] + k * np.pi / 2
                e = np.array([x - np.sin(h) * 7.5, y + 3.2, z - np.cos(h) * 7.5])
                f = np.array([x, y + 1.4, z]) - e; views.append((e, f / np.linalg.norm(f)))
        gz += st; row += 1
    return views

def engine_planes(f):
    """setupPlanes() из viewer/main.c: 4 внутренние нормали боковых плоскостей (не нормированы)"""
    fx, fy, fz = f; rx, rz = -fz, fx; rl = np.hypot(rx, rz)
    if rl < 1e-4: rx, rz, rl = 1., 0., 1.
    rx /= rl; rz /= rl
    ux, uy, uz = -rz * fy, rz * fx - rx * fz, rx * fy
    tv = np.tan(np.radians(FOVY / 2)) * 1.03; th = tv * ASPECT
    return np.array([[fx * th - rx, fy * th, fz * th - rz], [fx * th + rx, fy * th, fz * th + rz],
                     [fx * tv - ux, fy * tv - uy, fz * tv - uz], [fx * tv + ux, fy * tv + uy, fz * tv + uz]])

def bench(L, variants, path=None, res=512):
    rec = L['rec']; city = np.where(rec['owner'] == 0)[0]
    bb = rec['bb'][city].astype(np.float64); c = (bb[:, :3] + bb[:, 3:]) / 2
    rad = .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1)
    ni, nf = rec['ni'][city] // 3, rec['nf'][city] // 3
    nf = np.where(rec['flags'][city] & 2048, ni, nf)   # флаг 2048 (правки 224/237/251): ближняя на любой дальности
    pos = np.full(len(rec), -1); pos[city] = np.arange(len(city))
    views = bench_views(L)
    oracle = None
    if path is not None:
        vis = run_exact(path, [e for e, f in views], res)
        oracle = [pos[vis[vis[:, 0] == i, 1]] for i in range(len(views))]
    names = ['конус (движок v7)', 'пирамида'] + list(variants) + (['идеал (точная видимость)'] if oracle else [])
    res_ = {k: [] for k in names}; nodata = 0
    for i, (e, f) in enumerate(views):
        # coneOut(): сфера куска, дальность и LOD по сфере
        dv = c - e; dist = np.linalg.norm(dv, axis=1); fw = dv @ f
        side = np.sqrt(np.maximum(0, dist ** 2 - fw ** 2))
        cone = (dist - rad <= DRAW) & ~(side * .6 - fw * .8 > rad)
        # cullPiece() с O_PLANES: boxD2 <= 115^2, visBox (p-вершина ящика против каждой плоскости), LOD по boxD2
        bd = np.linalg.norm(np.maximum(0, np.maximum(bb[:, :3] - e, e - bb[:, 3:])), axis=1)
        planes = bd <= DRAW
        for n in engine_planes(f):
            pv = np.where(n > 0, bb[:, 3:], bb[:, :3]) - e
            planes &= pv @ n >= 0
        tri_c = np.where(dist - rad > LOD, nf, ni); tri = np.where(bd > LOD, nf, ni)
        masks = {'конус (движок v7)': cone, 'пирамида': planes}
        for name, P in variants.items():
            lst = cell_list(P, e[0], e[2]); m = planes
            if lst is None: nodata += name == next(iter(variants))
            else:
                allow = np.zeros(len(city), bool); allow[pos[lst.astype(np.int64)]] = True; m = planes & allow
            masks[name] = m
        if oracle:
            allow = np.zeros(len(city), bool); allow[oracle[i]] = True; masks['идеал (точная видимость)'] = planes & allow
        for name, m in masks.items(): res_[name].append((m.sum(), (tri_c if name == 'конус (движок v7)' else tri)[m].sum()))
    print(f'\n[2] кадры тест-прогона: {len(views)} видов ({len(views) // 4} точек x 4), без данных PVS (фолбэк): {nodata}')
    print(f'    {"вариант":<26}{"вызовы мед/p90/макс":>22}{"треуг. мед/p90/макс":>26}')
    for name, v in res_.items():
        a = np.array(v)
        print(f'    {name:<26}{np.median(a[:, 0]):>8.0f}{np.percentile(a[:, 0], 90):>7.0f}{a[:, 0].max():>7.0f}'
              f'{np.median(a[:, 1]) / 1e3:>10.1f}k{np.percentile(a[:, 1], 90) / 1e3:>7.1f}k{a[:, 1].max() / 1e3:>7.1f}k')

def layers_at(L, x, z):
    """слои карты высот в точке или в ближайшей непустой клетке в радиусе 6 м (как layersAt в pvs.c)"""
    hm, hc = L['hm'], L['hcell']
    gx, gz = int(np.floor((x - L['hox']) / hc)), int(np.floor((z - L['hoz']) / hc))
    rr = int(np.ceil(LRAD / hc)) + 1; best, bd = None, 1e30
    for dz in range(-rr, rr + 1):
        for dx in range(-rr, rr + 1):
            cx, cz = gx + dx, gz + dz
            if cx < 0 or cz < 0 or cx >= L['W'] or cz >= L['H']: continue
            c = hm[cz, cx]
            if (c == -32768).all(): continue
            x0, z0 = L['hox'] + cx * hc, L['hoz'] + cz * hc
            d = np.hypot(max(0, x0 - x, x - (x0 + hc)), max(0, z0 - z, z - (z0 + hc)))
            if d <= LRAD and d < bd: bd, best = d, c[c != -32768] * .01
    return best

def exact(L, path, n, res, seed, variants):
    P = L['pvs']; rng = np.random.default_rng(seed)
    data = [i for i, l in enumerate(P['lists']) if l is not None]
    eyes = []
    while len(eyes) < n:
        i = data[rng.integers(len(data))]; gx, gz = i % P['W'], i // P['W']
        x = P['ox'] + (gx + rng.random()) * P['cell']; z = P['oz'] + (gz + rng.random()) * P['cell']
        ls = layers_at(L, x, z)
        if ls is None: continue
        eyes.append((x, ls[rng.integers(len(ls))] + rng.uniform(1.2, 6.5), z))
    eyes = np.array(eyes)
    vis = run_exact(path, eyes, res)
    rec = L['rec']; bb = rec['bb'].astype(np.float64)
    e = eyes[vis[:, 0]]; lo, hi = bb[vis[:, 1], :3], bb[vis[:, 1], 3:]
    dist = np.linalg.norm(np.maximum(0, np.maximum(lo - e, e - hi)), axis=1)
    pix = vis[:, 2].astype(np.float64); fpix = pix * fogw(dist)
    print(f'\n[3] консервативность: {n} случайных глаз, кубическая карта {res}x{res} на грань '
          f'(1 пиксель ~ {(90 / res / (FOVY / 272)) ** 2:.1f} пикселя экрана PSP); видимых пар (глаз, кусок) {len(vis)}')
    for name, PV in variants.items():
        sets = []
        for x, _, z in eyes:
            l = cell_list(PV, x, z); sets.append(None if l is None else set(l.tolist()))
        miss = np.array([sets[ei] is not None and p not in sets[ei] for ei, p, _ in vis], bool)
        print(f'  {name}: пропущено {miss.sum()} пар из {len(vis)} ({100 * miss.mean():.2f}%); по пикселям '
              f'{100 * pix[miss].sum() / pix.sum():.4f}%, с учётом тумана {100 * fpix[miss].sum() / fpix.sum():.4f}%; '
              f'глаз с пропусками {len(set(vis[miss, 0].tolist()))} из {n}')
        for lo_, hi_ in ((0, 30), (30, 60), (60, 1e9)):
            b = (dist >= lo_) & (dist < hi_)
            if b.any():
                print(f'    {lo_:>3.0f}-{hi_ if hi_ < 1e9 else 999:>3.0f} м: пропущено {miss[b].sum():>5} из {b.sum():>6} пар '
                      f'({100 * miss[b].mean():5.2f}%), пикселей {pix[b & miss].sum():>8.0f} из {pix[b].sum():>10.0f}, '
                      f'макс. в одном пропуске {pix[b & miss].max() if (b & miss).any() else 0:.0f}')
        idx = np.where(miss)[0]; idx = idx[np.argsort(-fpix[idx])][:8]
        if len(idx):
            print('    худшие пропуски (по пикселям с туманом): глаз x y z | кусок флаги треуг. | дальность | пикселей (с туманом)')
            for j in idx:
                ei, p = vis[j, 0], vis[j, 1]
                print(f'      {eyes[ei, 0]:7.1f} {eyes[ei, 1]:6.1f} {eyes[ei, 2]:7.1f} | {p:5d} {rec["flags"][p]} {rec["ni"][p] // 3:6d} | '
                      f'{dist[j]:5.1f} м | {pix[j]:5.0f} ({fpix[j]:.0f})')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('level', nargs='?', default=str(ROOT / 'build/level.shr'))
    ap.add_argument('--eyes', type=int, default=300); ap.add_argument('--res', type=int, default=512)
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--no-exact', action='store_true')
    ap.add_argument('--pvs', default=str(PVS_BIN), help='бинарник pvs для точной видимости (по умолчанию tools/pvs)')
    a = ap.parse_args(); PVS_BIN = Path(a.pvs)
    L = load(a.level); P = L['pvs']
    if P is None: sys.exit('в файле нет PVS (заголовок @88 = 0)')
    if P['range'] >= 115: DRAW = float(P['range']); FOG0 = DRAW * .52   # правка 497: дальность списков из заголовка PVS1 (0 — 115)
    n = [len(l) for l in P['lists'] if l is not None]
    print(f'[1] PVS @{P["off"]}: сетка {P["W"]}x{P["H"]} по {P["cell"]:.0f} м от ({P["ox"]:.1f}, {P["oz"]:.1f}), '
          f'клеток с данными {len(n)}, пул {P["pool"]} ({P["pool"] * 2 / 2**20:.2f} MB); кусков в клетке '
          f'среднее {np.mean(n):.0f} медиана {np.median(n):.0f} p90 {np.percentile(n, 90):.0f} макс {max(n)} '
          f'(кусков города {(L["rec"]["owner"] == 0).sum()})')
    variants = {'PVS': P, 'PVS + соседи 3x3': dilate(P)}
    bench(L, variants, None if a.no_exact else a.level, a.res)
    if not a.no_exact: exact(L, a.level, a.eyes, a.res, a.seed, variants)
