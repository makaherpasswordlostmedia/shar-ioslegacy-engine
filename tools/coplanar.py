"""Поиск «слоёв» в уровне: почти параллельные треугольники разных кусков/текстур, лежащие друг над другом
с малым зазором (разметка, пешеходные переходы, тени деревьев, дорога над землёй). Именно они мигают на PSP
(16-битная глубина: соседние поверхности получают одно значение глубины, и то одна, то другая побеждает).

python tools/coplanar.py [build/level.shr] [--json out.json]
  -> зазоры по классам (непрозрачное / альфа-тест / полупрозрачное), текстуры-лидеры, точки для проверки,
     и дистанция, с которой при данной ближней плоскости слой начинает мигать.
Читает SHR7 (и старый индексный, и новый без индексов). Только чтение."""
import sys, struct, json, argparse
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
F_NOIDX, F_V12 = 16, 32


def load_city(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'SHR7', 'не SHR7'
    ntex, npc = struct.unpack_from('<II', b, 4)
    ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    P, T, FL, PI = [], [], [], []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        tex, fl, nv, ni, owner = r[6:11]; ox, oy, oz, sc = r[11:15]; off, nf, ci = r[15:18]
        if owner != 0 or ni == 0: continue
        base = cells[ci][9] + off
        if fl & F_NOIDX:
            vs = 12 if fl & F_V12 else 16
            raw = np.frombuffer(b, np.uint8, ni * vs, base).reshape(ni, vs)
            xyz = raw[:, vs - 6:vs].copy().view('<i2').reshape(ni, 3) if vs == 12 else raw[:, 8:14].copy().view('<i2').reshape(ni, 3)
        else:
            v = np.frombuffer(b, np.uint8, nv * 16, base).reshape(nv, 16)
            allxyz = v[:, 8:14].copy().view('<i2').reshape(nv, 3)
            io = base + ((nv * 16 + 15) & ~15)
            idx = np.frombuffer(b, '<u2', ni, io)
            xyz = allxyz[idx]
        w = xyz.astype(np.float64) * (sc / 32768.0) + np.array([ox, oy, oz])
        P.append(w.reshape(-1, 3, 3)); n = ni // 3
        T.append(np.full(n, tex)); FL.append(np.full(n, fl & 7)); PI.append(np.full(n, i))
    return np.concatenate(P), np.concatenate(T), np.concatenate(FL), np.concatenate(PI)


def _normals(P):
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    N = np.cross(e1, e2); A = np.linalg.norm(N, axis=1); ok = A > 1e-6
    N[ok] /= A[ok, None]
    return N, A, ok


def _pairs(P, T, PI, N, ok, own, Q, cell, maxgap, par, same_eps=None):
    """точки Q (M,3) треугольников own (M,) над/под треугольниками B (другой кусок или текстура, параллельно, зазор
    < maxgap, проекция точки внутри B) -> (M', 3): [номер точки, B, зазор со знаком по нормали B].
    same_eps: пары внутри одного куска и текстуры тоже (стопка полок одной текстуры — тоже слои), но не ближе same_eps
    (двусторонняя модель: копия той же поверхности)"""
    idx = np.nonzero(ok)[0]
    # решётка по xz: каждый треугольник B — во все клетки своего габарита
    lo = np.floor(P[idx].min(1)[:, [0, 2]] / cell).astype(np.int64); hi = np.floor(P[idx].max(1)[:, [0, 2]] / cell).astype(np.int64)
    span = (hi - lo + 1); cnt = span[:, 0] * span[:, 1]
    rep = np.repeat(np.arange(len(idx)), cnt)
    k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    gx = lo[rep, 0] + k % span[rep, 0]; gz = lo[rep, 1] + k // span[rep, 0]
    key = (gx + 100000) * 200000 + (gz + 100000)
    o = np.argsort(key, kind='stable'); key, bi = key[o], idx[rep[o]]
    ca = np.floor(Q[:, [0, 2]] / cell).astype(np.int64); akey = (ca[:, 0] + 100000) * 200000 + (ca[:, 1] + 100000)
    s, t = np.searchsorted(key, akey, 'left'), np.searchsorted(key, akey, 'right')
    res = []
    CH = 20000
    for c0 in range(0, len(Q), CH):
        a = np.arange(c0, min(c0 + CH, len(Q))); ss, tt = s[c0:c0 + CH], t[c0:c0 + CH]; m = tt - ss
        qi = np.repeat(a, m); bj = bi[np.repeat(ss, m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))]
        ai = own[qi]
        other = (PI[ai] != PI[bj]) | (T[ai] != T[bj])
        sel = other if same_eps is None else (ai != bj)
        qi, ai, bj, other = qi[sel], ai[sel], bj[sel], other[sel]
        d = np.einsum('ij,ij->i', N[ai], N[bj]); sel = np.abs(d) > par; qi, bj, other = qi[sel], bj[sel], other[sel]
        g = np.einsum('ij,ij->i', Q[qi] - P[bj, 0], N[bj]); sel = np.abs(g) < maxgap
        if same_eps is not None: sel &= other | (np.abs(g) >= same_eps)
        qi, bj, g = qi[sel], bj[sel], g[sel]
        # точка внутри B (в плоскости B)?
        q = Q[qi] - g[:, None] * N[bj]
        v0, v1, v2 = P[bj, 1] - P[bj, 0], P[bj, 2] - P[bj, 0], q - P[bj, 0]
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1); d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01; den[den == 0] = 1e-12
        u = (d11 * d20 - d01 * d21) / den; v = (d00 * d21 - d01 * d20) / den
        sel = (u >= -1e-3) & (v >= -1e-3) & (u + v <= 1 + 1e-3)
        res.append(np.stack([qi[sel], bj[sel], g[sel]], 1))
    return np.concatenate(res) if res else np.zeros((0, 3))


def analyze(P, T, FL, PI, cell=4.0, maxgap=0.30, par=0.995, same_eps=None):
    """-> R (K,3): [A, B, зазор центра A от плоскости B со знаком по нормали B], N (нормали), C (центры), A (2·площадь)"""
    N, A, ok = _normals(P); C = P.mean(1)
    idx = np.nonzero(ok)[0]
    R = _pairs(P, T, PI, N, ok, idx, C[idx], cell, maxgap, par, same_eps)
    if len(R): R[:, 0] = idx[R[:, 0].astype(int)]
    return R, N, C, A


def analyze_pts(P, T, PI, own, Q, cell=4.0, maxgap=0.30, par=0.995, same_eps=None):
    """то же для произвольных точек Q (M,3), принадлежащих треугольникам own (M,) (вершины наклейки: покрыта ли она
    подложкой целиком) -> (K,3): [номер точки, B, зазор со знаком по нормали B]"""
    N, A, ok = _normals(P)
    return _pairs(P, T, PI, N, ok, np.asarray(own), np.asarray(Q, np.float64), cell, maxgap, par, same_eps)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('shr', nargs='?', default=str(ROOT / 'build/level.shr'))
    ap.add_argument('--json'); ap.add_argument('--near', type=float, default=0.7); ap.add_argument('--h', type=float, default=3.3)
    a = ap.parse_args()
    P, T, FL, PI = load_city(a.shr)
    print(f'город: {len(P):,} треугольников (ближние версии), {len(np.unique(PI))} кусков')
    R, N, C, A = analyze(P, T, FL, PI)
    ai, bj, g = R[:, 0].astype(int), R[:, 1].astype(int), R[:, 2]
    # пара учитывается один раз на треугольник A: ближайший B
    o = np.lexsort((np.abs(g), ai)); ai, bj, g = ai[o], bj[o], g[o]
    first = np.r_[True, ai[1:] != ai[:-1]]; ai, bj, g = ai[first], bj[first], g[first]
    cls = lambda f: np.where(f & 2, 'blend', np.where(f & 1, 'alpha', 'opaque'))
    ca, cb = cls(FL[ai]), cls(FL[bj])
    area = 0.5 * A[ai]
    bins = [0, .002, .01, .03, .10, .30]
    print('\nтреугольники, лежащие над/под другой поверхностью (другой кусок или текстура), по зазору:')
    print('  класс A над B            ' + ''.join(f'{f"<{int(bins[i+1]*1000)}мм":>12}' for i in range(len(bins) - 1)) + '   площадь м²')
    for ka in ('opaque', 'alpha', 'blend'):
        for kb in ('opaque', 'alpha', 'blend'):
            m = (ca == ka) & (cb == kb)
            if not m.any(): continue
            h = np.histogram(np.abs(g[m]), bins)[0]
            print(f'  {ka:>7} на {kb:<7}        ' + ''.join(f'{x:>12,}' for x in h) + f'   {area[m].sum():>10,.0f}')
    # дистанция начала мигания: квант глубины dz(d) = d^2 (f-n) / (65535 f n) ~ d^2/(65535 n); у поверхности земли
    # с высоты глаза h разница глубин двух слоёв с зазором g ~ g*d/h -> мигает при d > g*65535*n/h (для «вертикальных»
    # слоёв, стен и вывесок, разница ~ g -> d > sqrt(g*65535*n))
    print(f'\nс ближней плоскостью {a.near} м (глаз {a.h} м над землёй) слой с зазором g начинает мигать примерно с:')
    for gg in (.002, .005, .01, .02, .05):
        print(f'   g = {gg*100:4.1f} см: земля {gg * 65535 * a.near / a.h:6.0f} м, стена {np.sqrt(gg * 65535 * a.near):5.0f} м')
    # текстуры-лидеры среди «опасных» (зазор < 3 см)
    m = np.abs(g) < .03
    print(f'\nопасные (зазор < 3 см): {m.sum():,} треуг., {area[m].sum():,.0f} м²; куски A: {len(np.unique(PI[ai[m]]))}')
    tk = {}
    for t_, ar, f_ in zip(T[ai[m]], area[m], FL[ai[m]]): tk.setdefault((int(t_), int(f_)), [0, 0.]); tk[(int(t_), int(f_))][0] += 1; tk[(int(t_), int(f_))][1] += ar
    print('  текстура A (флаги): треуг., м²')
    for (t_, f_), (n_, ar) in sorted(tk.items(), key=lambda kv: -kv[1][1])[:20]: print(f'    tex {t_:4d} fl {f_}: {n_:6,} {ar:9,.0f}')
    # точки (xz) с наибольшей площадью опасных слоёв — кандидаты для кадров в эмуляторе
    cc = C[ai[m]]; key = np.floor(cc[:, [0, 2]] / 20).astype(int); u, inv = np.unique(key, axis=0, return_inverse=True)
    s_ = np.bincount(inv.ravel(), weights=area[m]); top = np.argsort(-s_)[:15]
    print('  клетки 20 м с наибольшей площадью опасных слоёв (x z м²):')
    for i in top: print(f'    {u[i][0] * 20 + 10:7.0f} {u[i][1] * 20 + 10:7.0f} {s_[i]:8.0f}')
    if a.json:
        pieces = sorted({int(p) for p in PI[ai[m]]})
        Path(a.json).write_text(json.dumps(dict(pieces=pieces, n=int(m.sum()))))
        print(f'  куски с опасными слоями -> {a.json} ({len(pieces)})')


if __name__ == '__main__':
    main()
