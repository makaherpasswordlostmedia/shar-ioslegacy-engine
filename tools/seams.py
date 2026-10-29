#!/usr/bin/env python3
"""Швы и слои города — мерцание текстур на стыках (правка Роба 37, 28.09, видео 2:57–3:07, город у дома).

    python tools/seams.py [build/level.shr] [--rooms build/interiors-l1-gfx.bin] [--plant crack|noflag|noside|flip]
                          [--near X Z R]

Кусок SHR7 хранит вершины int16 от своего центра; мир = центр + v·sc/32768. Проверки (провал — код выхода 1):
  щели   — точки шва (вершины ≥ 2 кусков в пределах 4 мм), у которых мировые координаты кусков не совпадают бит в бит
           (считаются так же, как GE: float32 центр + int16·(sc/32768) в float32), а расходятся меньше чем на CRACK_MM —
           такую щель делает запись порта. Расхождения от шага решётки и больше — точки диска (сводка «в данных»).
  Т-стыки — вершина одного куска на ребре треугольника другого куска (не в его вершине, ближе 1 мм), ближняя версия,
           рёбра любой длины. GE растеризует ребро и ломаную через эту вершину по-разному — вдоль шва искрит фон.
           Провал, если хоть один (экспорт режет такие рёбра, tools/psp_export.py split_tjunctions).
  слои   — две параллельные поверхности с малым зазором g (наклейка A меньше подложки B; B пишет глубину). 16-бит глубина
           движка (viewer/main.c: NEAR_Z, дальняя DIST_LONG+10, DepthRange(65535, 0), GEQUAL) различает их на дальности d
           на g·K/d² единиц, K = 65536·n·f/(f−n) ≈ 98 900; плюс сдвиг слоёв LAYER_BIAS·этаж (флаги 64/256). Ближние версии
           рисуются до D = 100 м (комнаты — до 30 м, своя ближняя/дальняя плоскость). Для каждой пары:
             с её стороны A обязана быть сверху: не отсечена (кусок с отсечением — флаг 512, комнаты 128, O_CULL — и A
             смотрит на подложку -> «спрятана»), и перевес g·K/D² + Δсдвига ≥ 1 единицы (иначе «мигает»);
             со стороны подложки (если B оттуда видна: двусторонняя или обход B смотрит от A) сверху обязана быть B:
             A отсечена, или перевес B g·K/D² − Δсдвига ≥ 1 (иначе «просвечивает» — сдвиг протащил A сквозь B — или мигает).
           Суд симметричный (кто наклейка, не важно); «бутерброд» (закрыт с обеих сторон) не судится. Провал, если площадь
           «мигает»/«спрятана»/«просвечивает» больше допуска: 1% площади судимых пар, не меньше 2 м² (остаток сложных
           стопок; у уровня 1 — ~0.5%, до правки 29.09 — ~88%).
--near X Z R — отдельно считать в круге R м вокруг (X, Z) (у дома Симпсонов: 229 184 60).
--plant (заведомо плохой вход на копии файла, гейт обязан упасть):
  crack  — у куска шва у дома Симпсонов центр сдвинут на 0.3 мм (щель);
  noflag — у кусков-слоёв у дома сняты флаги 64/256/512 (слои без сдвига — мигают);
  noside — у кусков-слоёв со стороной снят флаг 512 (без отсечения — сдвиг протаскивает их сквозь подложку);
  flip   — у слоёв со стороной у дома обход развёрнут к подложке (отсечение прячет их)."""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[1]/"tools"))
from main_source import read_main
import argparse, re, struct, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import shr7read, coplanar   # noqa: E402


def world32(path, rooms=False):
    """вершины как их считает GE: float32(центр) + float32(int16) * float32(sc/32768) -> (N*3, 3) float32, номер куска"""
    b = Path(path).read_bytes()
    out_P, out_I = [], []
    def piece(base, fl, cnt, sc, o, pi):
        vs = 12 if fl & shr7read.F_V12 else 16
        raw = np.frombuffer(b, np.uint8, cnt * vs, base).reshape(cnt, vs)
        xyz = (raw[:, 6:12] if vs == 12 else raw[:, 8:14]).copy().view('<i2').reshape(cnt, 3).astype(np.float32)
        k = np.float32(sc) / np.float32(32768.0)
        w = np.asarray(o, np.float32)[None, :] + xyz * k
        out_P.append(w.astype(np.float32)); out_I.append(np.full(cnt, pi))
    if not rooms:
        ntex, npc = struct.unpack_from('<II', b, 4)
        ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
        cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
        for i in range(npc):
            r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
            tex, fl, nv, ni, own = r[6:11]; ox, oy, oz, sc = r[11:15]; off, nf, ci = r[15:18]
            if own != 0 or ni == 0 or not fl & shr7read.F_NOIDX: continue
            piece(cells[ci][9] + off, fl, ni, sc, (ox, oy, oz), i)
    return (np.concatenate(out_P), np.concatenate(out_I)) if out_P else (np.zeros((0, 3), np.float32), np.zeros(0, int))


CRACK_MM = 1.0


def cracks(W, PI, sel=None):
    """точки шва с расхождением: кластеры вершин разных кусков в пределах 4 мм (две решётки со сдвигом)
    -> (всего, щелей порта < CRACK_MM, макс мм, расхождений в данных)"""
    if sel is not None: W, PI = W[sel], PI[sel]
    bad = 0; mx = 0.0; seen_bad = set(); seen_tot = set(); seen_src = set()
    for shift in (0.0, 0.002):
        k = np.floor((W.astype(np.float64) + shift) / 0.004).astype(np.int64)
        key = (k[:, 0] * 1000003 + k[:, 1]) * 1000033 + k[:, 2]
        o = np.argsort(key, kind='stable'); ks = key[o]
        br = np.r_[0, np.nonzero(np.diff(ks))[0] + 1, len(ks)]
        size = np.diff(br); multi = np.nonzero(size >= 2)[0]
        for i in multi:
            g = o[br[i]:br[i + 1]]
            if len(np.unique(PI[g])) < 2: continue
            u = np.unique(W[g], axis=0); seen_tot.add(tuple(np.round(u[0].astype(np.float64) / 0.004).astype(int)))
            if len(u) > 1:
                sp = float((u.max(0) - u.min(0)).max())
                kk = tuple(np.round(u[0] / 0.004).astype(int))
                if sp < CRACK_MM / 1000:   # одна точка шва, разные биты — щель записи
                    if kk not in seen_bad: seen_bad.add(kk); bad += 1; mx = max(mx, sp)
                elif sp < 0.004: seen_src.add(kk)
    return len(seen_tot), bad, mx * 1000, len(seen_src)


def tjunctions(d, sel=None, tol=0.001):
    """вершины треугольников строго внутри ребра треугольника (ближняя версия, рёбра любой длины) ->
    (между кусками, внутри одного куска, «иголки» между кусками); sel — маска треугольников, чьи рёбра проверяем"""
    P = d['P']; PI = d['PI']
    V = P.reshape(-1, 3); VI = np.repeat(PI, 3)
    key3 = np.round(V / tol).astype(np.int64)
    _, inv = np.unique(np.c_[key3, VI], axis=0, return_index=True)   # точка × кусок: «чужая» — у любого другого куска
    V, VI = V[inv], VI[inv]
    cell = 2.0
    kv = np.floor(V[:, [0, 2]] / cell).astype(np.int64); vkey = (kv[:, 0] + 100000) * 200000 + (kv[:, 1] + 100000)
    o = np.argsort(vkey, kind='stable'); vkey_s = vkey[o]
    T = np.arange(len(P)) if sel is None else np.nonzero(sel)[0]
    E0 = np.concatenate([P[T, 0], P[T, 1], P[T, 2]]); E1 = np.concatenate([P[T, 1], P[T, 2], P[T, 0]]); EI = np.tile(PI[T], 3)
    ET = np.tile(np.arange(len(T)), 3); EK = np.repeat(np.arange(3), len(T))
    cross = same = needles = 0
    for c0 in range(0, len(E0), 100000):
        a, bb, ei = E0[c0:c0 + 100000], E1[c0:c0 + 100000], EI[c0:c0 + 100000]
        lo = np.floor((np.minimum(a, bb)[:, [0, 2]] - tol) / cell).astype(np.int64); hi = np.floor((np.maximum(a, bb)[:, [0, 2]] + tol) / cell).astype(np.int64)
        sp = hi - lo + 1; cnt = sp[:, 0] * sp[:, 1]
        rep = np.repeat(np.arange(len(a)), cnt); kk = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        key = (lo[rep, 0] + kk % sp[rep, 0] + 100000) * 200000 + (lo[rep, 1] + kk // sp[rep, 0] + 100000)
        s, t = np.searchsorted(vkey_s, key, 'left'), np.searchsorted(vkey_s, key, 'right'); m = t - s
        E = rep[np.repeat(np.arange(len(rep)), m)]; Vi = o[np.repeat(s, m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))]
        d_ = bb[E] - a[E]; l2 = (d_ * d_).sum(1); l2[l2 == 0] = 1e-18; tt = ((V[Vi] - a[E]) * d_).sum(1) / l2
        dist = np.linalg.norm(V[Vi] - (a[E] + tt[:, None] * d_), axis=1); Ln = np.sqrt(l2)
        hit = (dist < tol) & (tt * Ln > tol * 3) & ((1 - tt) * Ln > tol * 3)
        # «иголка»: разрез в этой точке (веер от третьей вершины) положил бы конец ребра ближе tol к новому ребру — это
        # две почти совпавшие вершины у конца ребра, не стык (tools/psp_export.py tj_needle); считаются отдельно
        hh = np.nonzero(hit)[0]; tri = ET[c0 + E[hh]]; kk_ = EK[c0 + E[hh]]; c3 = P[T[tri], (kk_ + 2) % 3]
        q = V[Vi[hh]]; dd = c3 - q; l2c = (dd * dd).sum(1); l2c[l2c == 0] = 1e-18
        def ldist(p_):
            t_ = ((p_ - q) * dd).sum(1) / l2c; return np.linalg.norm(p_ - (q + t_[:, None] * dd), axis=1)
        ndl = np.zeros(len(hit), bool); ndl[hh] = (ldist(a[E[hh]]) < tol) | (ldist(bb[E[hh]]) < tol)
        hit[hh[np.linalg.norm(q - c3, axis=1) < tol]] = False   # третья вершина самого треугольника («иголка» — сама у ребра) — не стык
        xp = VI[Vi] != ei[E]
        cross += int((hit & ~ndl & xp).sum()); same += int((hit & ~ndl & ~xp).sum()); needles += int((hit & ndl & xp).sum())
    return cross, same, needles


# ------------------------------------------------------------------------------------------------ слои (правки 37, 43)
F_SKY, F_DOUBLE, F_LAYER, F_SHELL, F_LAYER2, F_LSIDE, F_LAYER3 = 4, 8, 64, 128, 256, 512, 1024
D_CITY, D_ROOM = 100.0, 30.0   # м: до скольких рисуется ближняя версия куска города (LOD_DIST 50 м + клетка 40 м) / комната
COPLAN = 0.002                 # м: наклейка в плоскости подложки (с точностью решётки вершин 2^-9 м) — стороны нет, сверху та, что со сдвигом
SAND_GAP = 0.12                # м: подложки по обе стороны ближе этого — A закрыта с любой стороны («бутерброд»)
BUDGET_REL, BUDGET_MIN = 0.01, 2.0   # допуск остатка слоёв: 1% площади судимых пар, не меньше 2 м² (см. layer_notes)


def engine():
    """константы движка, от которых зависит глубина: viewer/main.c"""
    s = read_main(ROOT / 'viewer/main.c', errors="replace")
    def f(name):
        m = re.search(rf'#define {name}\s+\(?([0-9.]+)', s)
        if not m: raise SystemExit(f'seams: нет {name} в viewer/main.c')
        return float(m.group(1))
    m = re.search(r'#define O_DEFAULT \(([^)]*)\)', s)
    return dict(near=f('NEAR_Z'), far=f('DIST_LONG') + 10, bias=f('LAYER_BIAS'), rnear=f('ROOM_NEAR'), rfar=f('ROOM_FAR'),
                cull=bool(m and 'O_CULL' in m.group(1)))


def depth_k(n, f):
    """|dz_окна / dd| · d² для DepthRange(65535, 0) и перспективы с плоскостями n, f"""
    return 65536.0 * n * f / (f - n)


def layers(d, K, D, bias_unit, cull_all, rooms=False):
    """пары слоёв ближней версии (параллельно, центр одного над другим, зазор < D²/K; судится та пара, где нижняя пишет
    глубину) -> маски треугольников по исходам. Суд симметричен: с каждой стороны сверху обязана быть ближняя к зрителю,
    поэтому кто из двух «наклейка», не важно (в плоскости подложки — лишь бы сдвиг был разный). Треугольник с закрывающими
    (не меньше его) по обе стороны ближе SAND_GAP («бутерброд») закрыт отовсюду — не судится (сводка)"""
    P, FL, TEX, PI = d['P'], d['FL'], d['TEX'], d['PI']
    G = D * D / K                      # зазор, который глубина не различает на D при равном сдвиге
    R, N, C, A = coplanar.analyze(P, TEX, FL & 7, PI, maxgap=max(G, SAND_GAP), same_eps=COPLAN)   # и внутри куска
    ai, bj, g = R[:, 0].astype(int), R[:, 1].astype(int), R[:, 2]
    # «бутерброд»: закрывающие A (пишут глубину, не меньше её) по обе стороны (зазор ≥ COPLAN, до SAND_GAP)
    cv = ((FL[bj] & 2) == 0) & ((A[ai] <= A[bj] * 1.001) | ((FL[ai] & 2) != 0)) & (np.abs(g) >= COPLAN)
    ca, cs = ai[cv], np.sign(g[cv])[:, None] * N[bj[cv]]; ref = np.zeros((len(P), 3))
    if len(ca):
        o = np.lexsort((np.abs(g[cv]), ca)); f1 = np.r_[True, ca[o][1:] != ca[o][:-1]]; ref[ca[o][f1]] = cs[o][f1]
    sandA = np.zeros(len(P), bool); sandA[ca[np.einsum('ij,ij->i', cs, ref[ca]) < 0]] = True
    # судимая пара: нижняя (B) пишет глубину; если пишет только верхняя — пара переворачивается
    wa, wb = (FL[ai] & 2) == 0, (FL[bj] & 2) == 0
    sw = ~wb & wa
    g = np.where(sw, -g * np.sign(np.einsum('ij,ij->i', N[ai], N[bj])), g)
    ai, bj = np.where(sw, bj, ai), np.where(sw, ai, bj)
    use = wa | wb
    coplan = np.abs(g) < COPLAN
    use &= ~(coplan & (TEX[ai] == TEX[bj]))            # дубль той же текстуры в той же плоскости (двусторонняя модель) — одно и то же
    use &= (np.abs(g) < G)
    ai, bj, g, coplan = ai[use], bj[use], g[use], coplan[use]
    _, u = np.unique(np.stack([np.minimum(ai, bj), np.maximum(ai, bj)], 1), axis=0, return_index=True)   # пара — один раз
    ai, bj, g, coplan = ai[u], bj[u], g[u], coplan[u]
    lev = np.where(FL & F_LAYER, 1 + ((FL & F_LAYER2) != 0) + 2 * ((FL & F_LAYER3) != 0), 0)   # этаж слоя (viewer/main.c setFlags)
    dl = (lev[ai] - lev[bj]) * bias_unit
    side = np.sign(g)[:, None] * N[bj]
    culled = (FL & F_LSIDE) != 0
    if rooms: culled |= ((FL & F_SHELL) != 0) & ((FL & F_DOUBLE) == 0)
    elif cull_all: culled |= ((FL & (F_DOUBLE | F_SKY)) == 0)
    ag = np.abs(g) * K / (D * D)
    fA = np.einsum('ij,ij->i', N[ai], side) > 0      # A смотрит на сторону A (от B)
    fB = np.sign(g) > 0                               # B смотрит на сторону A (нормаль B · сторона = знак зазора)
    cA, cB = culled[ai], culled[bj]
    # что нарисовано, если смотреть со стороны A (зритель за A) и со стороны B (зритель за B): кусок с отсечением виден
    # только лицом к зрителю (CCW, sceGuFrontFace(GU_CCW))
    dA_a, dB_a = ~cA | fA, ~cB | fB
    dA_b, dB_b = ~cA | ~fA, ~cB | ~fB
    lside = (FL[ai] & F_LSIDE) != 0
    # со стороны A сверху обязана быть A. Её сторону не судим, если A — кусок с отсечением по голосованию видов (комнаты
    # 128, O_CULL), смотрящий на подложку: голосование сказало, что с этой стороны её не видят
    obsA = ~(cA & ~lside & ~fA) & ~sandA[ai]              # «бутерброд» A: со стороны A её закрывает другая поверхность
    hidA = obsA & ~coplan & ~dA_a & dB_a                         # A не нарисована, видна B — «спрятана»
    zA = obsA & dA_a & dB_a & np.where(coplan, dl == 0, ag + dl < 1)   # обе нарисованы, глубина их не разводит
    hid = hidA | (zA & ~coplan & (ag + dl < 0))                  # B всегда сверху A
    fl_a = zA & ~hid
    # со стороны B, если её оттуда видно: у пола/крыши — только сверху (A под ней), у стен — двусторонняя или обход B
    # смотрит от A (g < 0: tools/wind.c и tools/roomorient.py разворачивают кусок туда, откуда его видят). Сверху — B
    ground = np.abs(N[bj][:, 1]) > .7
    seenB = np.where(ground, side[:, 1] < 0, ((FL[bj] & F_DOUBLE) != 0) | (g < 0)) & ~coplan & ~sandA[bj]
    blB = seenB & ~dB_b & dA_b                                   # B не нарисована, видна A — «просвечивает»
    zB = seenB & dA_b & dB_b & (ag - dl < 1)
    bl = blB | (zB & (dl > 0))
    out = {}
    for nm, m in (('мигает', fl_a | (zB & (dl <= 0))), ('спрятана', hid), ('просвечивает', bl),
                  ('пар', np.ones(len(ai), bool))):
        t = np.zeros(len(P), bool); t[ai[m]] = True; out[nm] = t
    out['бутерброд'] = sandA
    out['A'] = A / 2; out['C'] = C; out['G'] = G
    return out


def layer_notes(name, L, near, fails, notes):
    """сводка по слоям и провал: плохих (мигает/спрятана/просвечивает) больше допуска BUDGET_REL от площади судимых
    пар (но не меньше BUDGET_MIN м²). Допуск — остаток сложных стопок, которые общее правило экспорта не разводит
    (этажей больше 4, спор сторон у полок и рам): у уровня 1 после правки 29.09 — ~0.5% площади пар, до правки — ~88%"""
    parts = []
    for k in ('пар', 'мигает', 'спрятана', 'просвечивает'):
        m = L[k]; s_ = f'{k} {int(m.sum()):,} ({L["A"][m].sum():,.1f} м²)'
        if near is not None: s_ += f' / у дома {int((m & near).sum()):,} ({L["A"][m & near].sum():,.1f} м²)'
        parts.append(s_)
    bad = L['мигает'] | L['спрятана'] | L['просвечивает']
    area, total = float(L['A'][bad].sum()), float(L['A'][L['пар']].sum())
    budget = max(BUDGET_REL * total, BUDGET_MIN)
    notes.append(f'слои {name} (зазор < {L["G"] * 1000:.0f} мм, треуг. A): ' + '; '.join(parts) +
                 f'; «бутерброд» (закрыт с обеих сторон, не судим) {int(L["бутерброд"].sum()):,}; плохих {area:,.1f} м² '
                 f'({100 * area / max(total, 1e-9):.2f}% площади пар), допуск {budget:,.1f} м²')
    if area > budget:
        i = int(np.nonzero(bad)[0][np.argmax(L['A'][bad])]); c = L['C'][i]
        fails.append(f'слои {name}: мигает {int(L["мигает"].sum()):,}, спрятано {int(L["спрятана"].sum()):,}, просвечивает '
                     f'{int(L["просвечивает"].sum()):,} треуг. — {area:,.1f} м² больше допуска {budget:,.1f} м²; '
                     f'крупнейший у ({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f})')


# ------------------------------------------------------------------------------------------------ подложенные ошибки
def _pieces(b, need, X=229.0, Z=184.0, R=60.0):
    """куски города с флагами need у (X, Z) в R м -> [(номер, смещение Rec.flags, флаги)]"""
    ntex, npc = struct.unpack_from('<II', b, 4); ptab, = struct.unpack_from('<I', b, 76)
    out = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII', b, ptab + 80 * i)
        cx, cz = (r[0] + r[3]) / 2, (r[2] + r[5]) / 2
        if r[10] == 0 and (r[7] & need) == need and np.hypot(cx - X, cz - Z) < R: out.append((i, ptab + 80 * i + 28, r[7]))
    return out


def plant(path, kind):
    """заведомо плохой вход -> путь к копии"""
    b = bytearray(Path(path).read_bytes())
    if kind == 'crack':   # у одного куска шва у дома Симпсонов центр сдвинут на 0.3 мм (как округление «по-своему»)
        W, PI = world32(path)
        near = np.nonzero(np.linalg.norm(W[:, [0, 2]] - np.array([229.0, 184.0], np.float32), axis=1) < 30)[0]
        k = np.round(W[near].astype(np.float64) / 0.004).astype(np.int64)
        from collections import defaultdict
        grp = defaultdict(set)
        for kk, pi in zip(map(tuple, k), PI[near]): grp[kk].add(int(pi))
        pi = min(next(s_ for s_ in grp.values() if len(s_) >= 2))
        ptab, = struct.unpack_from('<I', b, 76); o = ptab + 80 * pi + 44   # Rec.ox
        ox, = struct.unpack_from('<f', b, o); struct.pack_into('<f', b, o, ox + 0.0003)
        msg = f'у куска {pi} у дома Симпсонов центр сдвинут на 0.3 мм'
    elif kind == 'noflag':   # слои у дома без флагов — как до правки: без сдвига
        pcs = _pieces(b, F_LAYER)
        for i, o, fl in pcs: struct.pack_into('<I', b, o, fl & ~(F_LAYER | F_LAYER2 | F_LAYER3 | F_LSIDE))
        msg = f'у {len(pcs)} кусков-слоёв у дома Симпсонов сняты флаги 64/256/512/1024'
    elif kind == 'noside':   # слои со стороной без отсечения — сдвиг тащит их сквозь подложку
        pcs = _pieces(b, F_LSIDE, R=1e9)
        for i, o, fl in pcs: struct.pack_into('<I', b, o, fl & ~F_LSIDE)
        msg = f'у {len(pcs)} кусков-слоёв уровня снят флаг 512'
    elif kind == 'flip':     # обход слоёв со стороной у дома — к подложке: отсечение их прячет
        d = shr7read.load(path); C = d['P'].mean(1)
        m = ((d['FL'] & F_LSIDE) != 0) & (np.linalg.norm(C[:, [0, 2]] - np.array([229.0, 184.0]), axis=1) < 60)
        for off, vs in zip(d['OFF'][m], d['VS'][m]):
            off, vs = int(off), int(vs); v1 = bytes(b[off + vs:off + 2 * vs])
            b[off + vs:off + 2 * vs] = b[off + 2 * vs:off + 3 * vs]; b[off + 2 * vs:off + 3 * vs] = v1
        msg = f'у {int(m.sum())} треуг. слоёв со стороной у дома обход развёрнут к подложке'
    tmp = Path(tempfile.mkdtemp(prefix='seams_plant_')) / 'planted.shr'; tmp.write_bytes(bytes(b))
    print(f'подложено ({kind}): {msg}')
    return tmp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shr', nargs='?', default=str(ROOT / 'build/level.shr'))
    ap.add_argument('--rooms', default=None, help='interiors-l1-gfx.bin (по умолчанию рядом с уровнем, если есть; none — без комнат)')
    ap.add_argument('--near', nargs=3, type=float, default=[229.0, 184.0, 60.0])
    ap.add_argument('--plant', choices=('crack', 'noflag', 'noside', 'flip'))
    ap.add_argument('--tj', action='store_true', help='(для совместимости: Т-стыки считаются всегда)')
    a = ap.parse_args()
    shr = plant(a.shr, a.plant) if a.plant else Path(a.shr)
    rooms = None if a.rooms == 'none' else Path(a.rooms) if a.rooms else Path(a.shr).with_name('interiors-l1-gfx.bin')
    W, PI = world32(shr)
    X, Z, R = a.near; near = np.linalg.norm(W[:, [0, 2]] - np.array([X, Z], np.float32), axis=1) < R
    fails, notes = [], []
    t_all, b_all, m_all, s_all = cracks(W, PI)
    t_n, b_n, m_n, s_n = cracks(W, PI, near)
    notes.append(f'щели записи (< {CRACK_MM:g} мм, не бит в бит): {b_all:,} из {t_all:,} точек шва между кусками (макс {m_all:.3f} мм); '
                 f'у ({X:g}, {Z:g}) в {R:g} м: {b_n:,} из {t_n:,}')
    notes.append(f'расхождения ≥ {CRACK_MM:g} мм (точки на диске разные, для сведения): {s_all:,}, у дома {s_n:,}')
    if b_all: fails.append(f'щели по швам: {b_all:,} точек шва (у дома {b_n:,}) — вершины кусков не совпадают, шов мерцает')
    d = shr7read.load(shr); C = d['P'].mean(1); sel = np.linalg.norm(C[:, [0, 2]] - np.array([X, Z]), axis=1) < R
    tj_all, tj_same, tj_ndl = tjunctions(d); tj_near = tjunctions(d, sel)[0]
    notes.append(f'Т-стыки ближней версии между кусками: {tj_all:,}, у ({X:g}, {Z:g}) в {R:g} м — {tj_near:,} '
                 f'(для сведения: внутри одного куска {tj_same:,}; «иголки» — почти совпавшие вершины у конца ребра {tj_ndl:,})')
    if tj_all: fails.append(f'Т-стыки: {tj_all:,} (у дома {tj_near:,}) — вершина куска на ребре соседа, вдоль шва искрит фон')
    e = engine(); K = depth_k(e['near'], e['far'])
    notes.append(f'глубина: ближняя {e["near"]:g} м, дальняя {e["far"]:g} м, K = {K:,.0f}; сдвиг слоя {e["bias"]:g} ед.; '
                 f'O_CULL {"вкл" if e["cull"] else "выкл"}')
    layer_notes('города', layers(d, K, D_CITY, e['bias'], e['cull']), sel, fails, notes)
    if rooms is not None and rooms.exists():
        Kr = depth_k(e['rnear'], e['rfar'])
        for nm, dr in shr7read.load_rooms(rooms).items():
            if not len(dr['P']): continue
            layer_notes(f'комнаты {nm}', layers(dr, Kr, D_ROOM, e['bias'], False, rooms=True), None, fails, notes)
            tr, ts, tn = tjunctions(dr)
            notes.append(f'Т-стыки комнаты {nm} между кусками: {tr:,} (для сведения: внутри куска {ts:,}, «иголки» {tn:,})')
            if tr: fails.append(f'Т-стыки комнаты {nm}: {tr:,}')
    print('FAIL: ' + fails[0] if fails else 'PASS: швы бит в бит, Т-стыков нет, слои разведены по глубине (остаток сложных стопок — в допуске)')
    for f_ in fails[1:]: print('  ещё: ' + f_)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
