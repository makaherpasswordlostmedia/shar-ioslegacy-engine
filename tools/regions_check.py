"""Гейт правки 95 (L1 F11-2, крыша заправки F10-7): с места игрока не рисуются куски регионов, которых оригинал там не держит.

Проверка по файлу level.shr и диску, независимо от того, как экспортёр считал маску (tools/regions_export.py):
  - откуда треугольник: дальние версии кусков города — исходные треугольники диска (рёбра <= 28 м), их вершины сверяются с
    вершинами мешей каждого региона диска (допуск 4 мм) — так узнаётся регион и у старого файла без REG1;
  - где стоит игрок: глаз в центре каждой клетки PVS 20 м, под ним земля коллизии (Intersect) регионов диска — «дом»;
  - что рисует движок: список PVS клетки (вид с земли) и все куски в радиусе (вид с крыши/в прыжке — PVS не годится,
    viewer/main.c pvsEyeOk), отфильтрованные маской REG1 клетки, как viewer/main.c cullPiece (без REG1 или --no-reg — всё);
  - нарушение: в радиусе R (60 м) рисуется треугольник региона A, который оригинал не держит вместе НИ С ОДНИМ регионом
    земли под глазом (матрица «вместе не грузятся» — ZoneEvent/телепорты/миссии диска, regions_export.dyna_states);
  - дыры: кусок региона земли под глазом в радиусе R не рисуется из-за маски — тоже нарушение.
Красный на старом правиле (старый файл или --no-reg): у заправки рисуется холм/дома/деревья l1r1. Зелёный — ноль нарушений.
  python tools/regions_check.py [build/level.shr] [--level 1] [--radius 60] [--no-reg] [--at "x z" ...]
Выход 0 — зелёный, 1 — нарушения, 2 — ошибка файла."""
import argparse, json, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import regions_export as RX

TOL = 0.004   # м: вершина файла (решётка 2^-9, сварка <= 1.2 мм) против вершины диска


def load_shr(path):
    b = Path(path).read_bytes()
    if b[:4] != b'SHR7': raise SystemExit(f'{path}: не SHR7')
    npc, = struct.unpack_from('<I', b, 8)
    hox, hoz, hcell = struct.unpack_from('<3f', b, 56); hw, hh = struct.unpack_from('<2i', b, 68)
    table, ncell, cello, pvso = struct.unpack_from('<4I', b, 76)
    recs = np.frombuffer(b, np.dtype([('bb', '<f4', 6), ('tex', '<i4'), ('flags', '<u4'), ('nv', '<u4'), ('ni', '<u4'), ('owner', '<u4'),
                                      ('o', '<f4', 3), ('sc', '<f4'), ('off', '<u4'), ('nf', '<u4'), ('cell', '<u4'), ('pad', '<u4', 2)]), npc, table)
    cells = np.frombuffer(b, np.dtype([('bb', '<f4', 6), ('first', '<u4'), ('n', '<u4'), ('owner', '<u4'), ('off', '<u4'), ('size', '<u4'),
                                       ('pad', '<u4')]), ncell, cello)
    hm = np.frombuffer(b, '<i2', hw * hh * 4, 104).reshape(hh, hw, 4)
    pvs = None
    if pvso and b[pvso:pvso + 4] == b'PVS1':
        ox, oz, cell = struct.unpack_from('<3f', b, pvso + 4); W, H, pool = struct.unpack_from('<3I', b, pvso + 16)
        ent = np.frombuffer(b, '<u4', W * H * 2, pvso + 32).reshape(H, W, 2)
        pl = np.frombuffer(b, '<u2', pool, pvso + 32 + W * H * 8)
        pvs = dict(ox=ox, oz=oz, cell=cell, W=W, H=H, ent=ent, pool=pl)
    return dict(buf=b, recs=recs, cells=cells, hm=hm, hox=hox, hoz=hoz, hcell=hcell, hw=hw, hh=hh, pvs=pvs, reg=RX.read_section(b))


def far_tris(S, k):
    """дальние треугольники куска k (мир, (n,3,3))"""
    r = S['recs'][k]; c = S['cells'][r['cell']]; base = int(c['off']) + int(r['off'])
    vs = 12 if r['flags'] & 32 else 16; po = 6 if vs == 12 else 8
    if not r['flags'] & 16:   # старый вид с индексами: вершины 16 Б, затем индексы ближних и дальних
        V = np.frombuffer(S['buf'], np.uint8, int(r['nv']) * 16, base).reshape(-1, 16)
        q = V[:, 8:14].copy().view('<i2').reshape(-1, 3).astype(np.float64)
        io = base + ((int(r['nv']) * 16 + 15) & ~15); fo = io + ((int(r['ni']) * 2 + 15) & ~15)
        idx = np.frombuffer(S['buf'], '<u2', int(r['nf']), fo).astype(np.int64)
        P = np.asarray(r['o'], np.float64) + q * (float(r['sc']) / 32768.)
        return P[idx].reshape(-1, 3, 3)
    n = int(r['nv']); V = np.frombuffer(S['buf'], np.uint8, n * vs, base).reshape(-1, vs)
    q = V[:, po:po + 6].copy().view('<i2').reshape(-1, 3).astype(np.float64)
    P = np.asarray(r['o'], np.float64) + q * (float(r['sc']) / 32768.)
    return P[int(r['ni']):int(r['ni']) + int(r['nf'])].reshape(-1, 3, 3)


def near_tris(S, k):
    """ближние треугольники куска k (мир, (n,3,3)) — сведение 03.10: у уровня после правки швов 224/237/251 дальних версий нет
    (флаг куска 2048), регион куска узнаётся по ближним"""
    r = S['recs'][k]; c = S['cells'][r['cell']]; base = int(c['off']) + int(r['off'])
    vs = 12 if r['flags'] & 32 else 16; po = 6 if vs == 12 else 8
    if not r['flags'] & 16:
        V = np.frombuffer(S['buf'], np.uint8, int(r['nv']) * 16, base).reshape(-1, 16)
        q = V[:, 8:14].copy().view('<i2').reshape(-1, 3).astype(np.float64)
        io = base + ((int(r['nv']) * 16 + 15) & ~15)
        idx = np.frombuffer(S['buf'], '<u2', int(r['ni']), io).astype(np.int64)
        P = np.asarray(r['o'], np.float64) + q * (float(r['sc']) / 32768.)
        return P[idx].reshape(-1, 3, 3)
    n = int(r['nv']); V = np.frombuffer(S['buf'], np.uint8, n * vs, base).reshape(-1, vs)
    q = V[:, po:po + 6].copy().view('<i2').reshape(-1, 3).astype(np.float64)
    P = np.asarray(r['o'], np.float64) + q * (float(r['sc']) / 32768.)
    return P[:int(r['ni'])].reshape(-1, 3, 3)


def disk_regions(level):
    """-> имена регионов, {регион: вершины рисунка (n,3)}, {регион: треугольники коллизии}"""
    import convert as cv
    tmp = ROOT / 'build' / 'tmp_conv'; tmp.mkdir(parents=True, exist_ok=True); cv.OUT = tmp
    from convert import Converter, GAME
    from p3d import read
    names = RX.level_regions(level); art = GAME / 'art'
    conv = Converter(); vis, col = {}, {}
    for path in sorted(art.glob(f'l{level}*.p3d')):
        try: conv.resources(read(path))
        except Exception: pass
    for p in sorted(art.glob(f'l{level}*.p3d')):
        nm = p.stem.lower()
        if nm not in names: continue
        conv.export(p, f'rchk_{nm}')
        meta = json.loads((tmp / f'rchk_{nm}.json').read_text()); raw = (tmp / f'rchk_{nm}.bin').read_bytes()
        Vs = []
        for obj in meta['objects']:
            M = np.array(obj['matrix'], np.float64).reshape(4, 4)
            for prim in meta['meshes'].get(obj['mesh'], []):
                at = prim['attributes']
                pos = np.frombuffer(raw, '<f4', at['position'][1], at['position'][0]).reshape(-1, 3)
                Vs.append((np.c_[pos, np.ones(len(pos))] @ M)[:, :3])
        vis[nm] = np.concatenate(Vs) if Vs else np.zeros((0, 3))
        if meta.get('collision'):
            o, n = meta['collision']; col[nm] = np.frombuffer(raw, '<f4', n, o).reshape(-1, 3, 3).astype(np.float64)
        for ext in ('json', 'bin'): (tmp / f'rchk_{nm}.{ext}').unlink()
    return names, vis, col


def vertex_index(names, vis):
    """ключи вершин (сетка TOL с соседями) -> регион (−2 — несколько регионов)"""
    keys, regs = [], []
    for r, nm in enumerate(names):
        V = vis.get(nm)
        if V is None or not len(V): continue
        for dx in (-TOL, TOL):
            for dy in (-TOL, TOL):
                for dz in (-TOL, TOL):
                    q = np.floor((V + (dx, dy, dz)) / (2 * TOL)).astype(np.int64)
                    keys.append((q[:, 0] * 1000003 + q[:, 1]) * 1000033 + q[:, 2]); regs.append(np.full(len(V), r, np.int64))
    K = np.concatenate(keys); R = np.concatenate(regs)
    o = np.lexsort((R, K)); K, R = K[o], R[o]
    u, first = np.unique(K, return_index=True)
    last = np.r_[first[1:], len(K)] - 1
    reg = np.where(R[first] == R[last], R[first], -2)
    return u, reg


def tri_regions(T, u, reg):
    """треугольники файла -> регион диска (все три вершины в одном регионе), −1 — не опознан"""
    q = np.floor(T.reshape(-1, 3) / (2 * TOL)).astype(np.int64)
    k = (q[:, 0] * 1000003 + q[:, 1]) * 1000033 + q[:, 2]
    i = np.clip(np.searchsorted(u, k), 0, len(u) - 1); r = np.where(u[i] == k, reg[i], -1).reshape(-1, 3)
    return np.where((r[:, 0] == r[:, 1]) & (r[:, 1] == r[:, 2]) & (r[:, 0] >= 0), r[:, 0], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('shr', nargs='?', default=str(ROOT / 'build/level.shr'))
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--radius', type=float, default=60.)
    ap.add_argument('--no-reg', action='store_true', help='как движок без правки 95: все регионы (отрицательный контроль)')
    ap.add_argument('--at', action='append', default=[], help='"x z" — подробно о точке')
    a = ap.parse_args()
    S = load_shr(a.shr)
    names, vis, col = disk_regions(a.level); nR = len(names)
    states, _ = RX.dyna_states(a.level, names)
    co = np.zeros((nR, nR), bool)
    for St in states:
        ix = [r for r in range(nR) if St >> r & 1]
        for r in ix: co[r, ix] = True
    u, vreg = vertex_index(names, vis)
    reg = None if a.no_reg else S['reg']
    if reg is not None and reg['names'] != names: print(f'REG1 файла {reg["names"]} != регионы диска {names}'); return 2
    city = np.nonzero(S['recs']['owner'] == 0)[0]
    # регион дальних треугольников каждого куска города (по вершинам диска) и их центры
    info = {}
    nearOnly = 0
    for k in city:
        T = far_tris(S, k)
        if not len(T):   # только ближняя версия (флаг 2048, правка швов 03.10): ближние разрезаны по Т-стыкам и юбкам, новые точки
            T = near_tris(S, k)   # разрезов вершинами диска не являются — регион куска голосованием вершин, совпавших с диском
            if not len(T): continue
            nearOnly += 1
            rr = tri_regions(T, u, vreg)
            if (rr < 0).any():
                q = np.floor(T.reshape(-1, 3) / (2 * TOL)).astype(np.int64); kk = (q[:, 0] * 1000003 + q[:, 1]) * 1000033 + q[:, 2]
                i = np.clip(np.searchsorted(u, kk), 0, len(u) - 1); vr = np.where(u[i] == kk, vreg[i], -1); vr = vr[vr >= 0]
                if len(vr): rr = np.full(len(T), int(np.bincount(vr).argmax()))
        else:
            rr = tri_regions(T, u, vreg)
        c = T.mean(1)
        info[int(k)] = (rr, c)
    known = sum(int((v[0] >= 0).sum()) for v in info.values()); tot = sum(len(v[0]) for v in info.values())
    # земля коллизии регионов (4 м)
    pv = S['pvs']
    if pv is None: print('нет PVS1 — проверка по спискам невозможна'); return 2
    ox, oz, W, H, CELLP = pv['ox'], pv['oz'], pv['W'], pv['H'], pv['cell']
    k4 = int(round(CELLP / 4.0))
    C = np.stack([RX.cover(col.get(nm, np.zeros((0, 3, 3))), ox, oz, W * k4, H * k4, 4.0) for nm in names])
    pieces_xz = {k: v[1][:, [0, 2]] for k, v in info.items()}
    viol_pvs, viol_all, holes, rows = 0, 0, 0, []
    focus = [tuple(float(t) for t in s.split()) for s in a.at]
    def mask_at(x, z):
        if reg is None: return (1 << nR) - 1
        gx = int(np.floor((x - reg['ox']) / reg['cell'])); gz = int(np.floor((z - reg['oz']) / reg['cell']))
        return int(reg['mask'][gz, gx]) if 0 <= gx < reg['W'] and 0 <= gz < reg['H'] else (1 << nR) - 1
    for gz in range(H):
        for gx in range(W):
            e0, cnt = pv['ent'][gz, gx]
            if cnt == 0xFFFFFFFF: continue
            ex, ez = ox + (gx + .5) * CELLP, oz + (gz + .5) * CELLP
            fx, fz = gx * k4 + k4 // 2, gz * k4 + k4 // 2
            home = [r for r in range(nR) if C[r, max(0, fz - 1):fz + 2, max(0, fx - 1):fx + 2].any()]
            if not home: continue
            bad = [A for A in range(nR) if all(not co[A, h] for h in home)]
            m = mask_at(ex, ez)
            lst = set(int(x) for x in pv['pool'][e0:e0 + cnt])
            near = [k for k, xz in pieces_xz.items() if np.hypot(xz[:, 0] - ex, xz[:, 1] - ez).min() <= a.radius]
            vp = va = hl = 0; who = {}
            for k in near:
                rr, c = info[k]; d = np.hypot(c[:, 0] - ex, c[:, 2] - ez) <= a.radius
                rg = int(S['recs'][k]['pad'][0])
                drawn = (rg == 0 or rg > nR or (m >> (rg - 1)) & 1) if reg is not None else True
                for A in set(rr[d].tolist()):
                    if A < 0: continue
                    n_ = int((rr[d] == A).sum())
                    if A in bad and drawn:
                        va += n_; who[names[A]] = who.get(names[A], 0) + n_
                        if k in lst: vp += n_
                    if A in home and not drawn: hl += n_
            viol_pvs += vp; viol_all += va; holes += hl
            if va or hl: rows.append((va, vp, hl, ex, ez, [names[h] for h in home], who))
            for fx_, fz_ in focus:
                if abs(fx_ - ex) <= CELLP / 2 and abs(fz_ - ez) <= CELLP / 2:
                    print(f'точка ({fx_:g} {fz_:g}) клетка ({ex:.0f} {ez:.0f}): земля {[names[h] for h in home]}, маска '
                          f'{[names[r] for r in range(nR) if m >> r & 1]}; чужих треугольников в {a.radius:g} м: PVS {vp}, с крыши {va} {who}; дыр {hl}')
    rule = 'все регионы (как до правки 95)' if reg is None else 'маска REG1'
    print(f'{Path(a.shr).name}: правило движка — {rule}; кусков города {len(city)}, треугольников {tot:,} (кусков только с ближней версией {nearOnly}), опознано по диску {known:,}')
    print(f'нарушения в радиусе {a.radius:g} м от глаза (клетки PVS с землёй): треугольников регионов, которые оригинал с этой земли '
          f'не держит, — в списках PVS {viol_pvs:,}, с крыши/в прыжке (все куски) {viol_all:,}; дыр (свой регион не рисуется) {holes:,}')
    rows.sort(key=lambda r: -r[0] - r[2])
    for va, vp, hl, ex, ez, home, who in rows[:8]:
        print(f'  клетка ({ex:6.0f} {ez:6.0f}) земля {home}: чужих {va} (в PVS {vp}) {who}; дыр {hl}')
    ok = viol_all == 0 and viol_pvs == 0 and holes == 0
    print('ЗЕЛЁНЫЙ' if ok else 'КРАСНЫЙ')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
