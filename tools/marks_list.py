#!/usr/bin/env python3
"""№912 разметка дорог слоем (Роб 23.10: «убрать все текстуры, в том числе асфальта»): дорожные текстуры, у которых рисунок — тонкая разметка на ровном асфальте
(штрихи, полосы, зебра, надпись STOP), рисуются заливкой асфальта с шумом, а разметка — векторными многоугольниками поверх, по одному вызову на клетку, без текстуры.

  python3 tools/marks_list.py level.shr [flat912.bin] [marks912.bin] [--cap N]

Что делает: 1) из дорожной текстуры (ground, рисунок не вырезами) делит точки на асфальт и до трёх цветов разметки (ближайший из цветов по записи палитры) и режет разметку на
прямоугольники по строкам (прямоугольников не больше CAP — иначе рисунок остаётся текстурой: люк, органическая тропа); 2) для каждого треугольника кусков города с этой текстурой
(ближняя версия, все куски текстуры должны быть непрозрачными кусками города) режет прямоугольники по треугольнику в пространстве UV на всех повторах текстуры (u16/256, как у GE)
и переносит многоугольники в мир (барицентрами), цвет света берёт интерполяцией цвета вершин; 3) пишет marks912.bin и ДОПИСЫВАЕТ в flat912.bin вид 3 («земля с шумом + разметка») для таких текстур.
Формат MRK1: 'MRK1', ntex, подпись, ncell, ncls (u32); ncell × {first, count} (вершины по 3 на треугольник); ncls × RGB0 (цвета разметки до кривой тона); вершины по 12 байт: x, y, z int16 (оси кусков клетки), свет RGB, класс цвета, 0, 0. Старое описание ниже:
  x,y,z int16 (метры × 128 от начала клетки: центр ящика клетки, как cl[].cx/cz — абсолютные в файле клеток, см. ниже), свет RGB 3 байта, цвет разметки (исходный, до кривой тона) RGB 3 байта.
Начало клетки — центр ящика клетки из таблицы клеток level.shr (float bb): cx = (bb0 + bb3)/2, y = 0, cz = (bb2 + bb5)/2. Цвет разметки движок прогоняет через кривую тона мультика при загрузке и при смене настроек."""
import struct, sys, collections
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flat_list as F

CAP = 130
CLS_TOL = 0.05       # допуск совпадения отображения UV -> мир, м на повтор (квантование вершин)
BASE_MAX_L = 130.0   # яркость асфальта не выше (0..255)
MARK_LIGHTER = 35.0  # разметка светлее асфальта не меньше чем на столько
SLIVER = 0.06       # кусок штриха меньше этой доли своего прямоугольника не рисуется
SMALL_AREA = 1.0     # штрих мельче (площадь в мире, м²) считается мелочью: движок рисует его только вблизи (marks912 группа small)
MARK_MIX = 0.9      # цвет разметки чуть ближе к асфальту (в текстуре край размыт фильтром)
MARK_MIN_D = 70.0   # цвет разметки не ближе этого (RGB) к асфальту
DEBUG = '--debug' in sys.argv
CLASS_R = 50.0


def rect_rows(mask):
    """маска (h, w) bool -> список прямоугольников (x0, y0, x1, y1) вертикальным слиянием одинаковых серий по строкам"""
    h, w = mask.shape; open_ = {}; out = []
    for y in range(h + 1):
        runs = []
        if y < h:
            row = mask[y]; x = 0
            while x < w:
                if row[x]:
                    x0 = x
                    while x < w and row[x]: x += 1
                    runs.append((x0, x))
                else: x += 1
        cur = {}
        for r in runs:
            if r in open_: cur[r] = open_.pop(r)
            else: cur[r] = y
        for r, y0 in open_.items(): out.append((r[0], y0, r[1], y))
        open_ = cur
    return out


def components(mask):
    """связные компоненты маски (4-связность) -> список (маска точек, bbox)"""
    h, w = mask.shape; seen = np.zeros_like(mask, bool); out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                st = [(y, x)]; seen[y, x] = True; pts = []
                while st:
                    cy, cx = st.pop(); pts.append((cy, cx))
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]: seen[ny, nx] = True; st.append((ny, nx))
                out.append(pts)
    return out


def rects_of(mask):
    """маска -> прямоугольники: компонента, заполняющая свой ящик на 80 % и больше, — один прямоугольник (штрих, полоса зебры); иначе серии по строкам"""
    out = []
    for pts in components(mask):
        ys = [p[0] for p in pts]; xs = [p[1] for p in pts]; y0, y1, x0, x1 = min(ys), max(ys) + 1, min(xs), max(xs) + 1
        if len(pts) >= 0.8 * (y1 - y0) * (x1 - x0): out.append((x0, y0, x1, y1)); continue
        m = np.zeros(mask.shape, bool)
        for (y, x) in pts: m[y, x] = True
        out += rect_rows(m)
    return out


def majority(m):
    """чистка маски по 8 соседям: точка остаётся, если рядом есть ещё хотя бы одна (одиночное зерно уходит, тонкая линия остаётся); пустая точка, окружённая ≥ 6 соседями, заполняется"""
    p = np.pad(m.astype(np.int32), 1); n = sum(p[dy:dy + m.shape[0], dx:dx + m.shape[1]] for dy in range(3) for dx in range(3)) - m.astype(np.int32)
    return np.where(m, n >= 1, n >= 6)


def analyse_texture(f, t):
    """-> dict(base, classes=[RGB], rects=[[(x0,y0,x1,y1)...] по классам], w, h) или None"""
    pal = t['pal']; px = F.indices(f, t); cnt = np.bincount(px.ravel(), minlength=256); alpha = pal[:, 3]
    tot = int(cnt.sum())
    if not tot or (int(cnt[alpha < 16].sum())) * 50 > tot: return None
    c1 = F.cluster(pal, cnt)
    if c1 is None: return None
    base = c1[1]; rgb = pal[:, :3].astype(float)
    d = np.sqrt(((rgb - base) ** 2).sum(axis=1))
    far_any = d[px] > 55.0; share0 = float(far_any.mean())
    strong = d[px] > 70.0
    if not strong.any() or share0 > 0.45: return None
    # цвета разметки: средние по сильным точкам, жадно (радиус CLASS_R2), не больше трёх классов; остальные — к ближайшему
    cols = []; ids = px[strong]; w = np.bincount(ids, minlength=256)
    for j in np.argsort(-w):
        if w[j] == 0: break
        for c in cols:
            if np.sqrt(((rgb[j] - c['col']) ** 2).sum()) <= 80.0: c['m'].append(j); break
        else:
            if len(cols) < 3: cols.append(dict(col=rgb[j].copy(), m=[j]))
            else: min(cols, key=lambda c: np.sqrt(((rgb[j] - c['col']) ** 2).sum()))['m'].append(j)
        for c in cols:
            ww = np.array([w[q] for q in c['m']], float); c['col'] = (rgb[c['m']] * ww[:, None]).sum(axis=0) / ww.sum()
    if min(np.sqrt(((c['col'] - base) ** 2).sum()) for c in cols) < MARK_MIN_D: return None
    lum = lambda c: .299 * c[0] + .587 * c[1] + .114 * c[2]
    if lum(base) > BASE_MAX_L: return None                                            # асфальт тёмный: светлые плиты тротуара, булыжник — не дорога
    cols = [c for c in cols if lum(c['col']) >= lum(base) + MARK_LIGHTER]; 
    if not cols: return None                                                          # разметка светлее асфальта (линии, зебра); тёмные швы и трещины — не разметка
    mask = majority(far_any)
    # класс — по компоненте: ближайший цвет разметки к среднему цвету точек компоненты (край штриха не рвётся между классами)
    cc = np.array([c['col'] for c in cols]); P = rgb[px]
    rects = [[] for _ in cols]; total = 0
    for pts in components(mask):
        ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts]); mean = P[ys, xs].mean(axis=0)
        k = int(np.argmin(np.sqrt(((cc - mean) ** 2).sum(axis=1))))
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        if len(pts) >= 0.8 * (y1 - y0) * (x1 - x0): r = [(int(x0), int(y0), int(x1), int(y1))]
        else:
            m = np.zeros(mask.shape, bool); m[ys, xs] = True; r = rect_rows(m)
        rects[k] += r; total += len(r)
    share = float(mask.mean()); h, w2 = px.shape
    if DEBUG: print('  текстура', round(share, 3), [len(x) for x in rects], [tuple(np.rint(c['col']).astype(int)) for c in cols])
    big = max((r[2] - r[0]) * (r[3] - r[1]) for rr in rects for r in rr) / float(h * w2) if total else 1.0
    if share > 0.50 or total > CAP or total == 0 or big > 0.25 or (share > 0.2 and big < 0.03): return None   # разметка тонкая: крупные пятна, доски, градиенты — рисунок, не разметка
    return dict(base=base, classes=[np.rint(base + (c['col'] - base) * MARK_MIX).astype(int) for c in cols], rects=rects, w=w2, h=h, share=share, n=total)


def clip_poly(poly, a, b, c):
    """полигон (список (x,y)) ∩ полуплоскость a*x + b*y + c >= 0"""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]; sp = a * p[0] + b * p[1] + c; sq = a * q[0] + b * q[1] + c
        if sp >= 0: out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def tri_poly(rect_uv, tri):
    """прямоугольник (u0,v0,u1,v1) ∩ треугольник tri (3,2) -> полигон или []"""
    u0, v0, u1, v1 = rect_uv
    poly = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    s = 1.0 if ((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1]) - (tri[1][1] - tri[0][1]) * (tri[2][0] - tri[0][0])) > 0 else -1.0
    for i in range(3):
        p, q = tri[i], tri[(i + 1) % 3]
        # ребро p->q: полуплоскость слева (для s=+1)
        a = -(q[1] - p[1]) * s; b = (q[0] - p[0]) * s; c = -(a * p[0] + b * p[1])
        poly = clip_poly(poly, a, b, c)
        if len(poly) < 3: return []
    return poly


def decode_color(raw, vs):
    if vs == 12:
        c = raw[:, 4:6].copy().view('<u2').reshape(-1).astype(np.int32)
        r = (c & 31) * 255 // 31; g = ((c >> 5) & 63) * 255 // 63; b = (c >> 11) * 255 // 31
        return np.stack([r, g, b], axis=1).astype(float)
    return raw[:, 4:7].astype(float)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    global CAP
    if '--cap' in sys.argv: CAP = int(sys.argv[sys.argv.index('--cap') + 1]); a = [x for x in a if x != str(CAP)]
    emit = sys.argv[sys.argv.index('--emit') + 1] if '--emit' in sys.argv else None   # flat | marks — один из двух файлов в --out (для правил сборки tools/ship_rules.txt); без --emit — оба рядом с level.shr
    if '--emit' in sys.argv: a = [x for x in a if x not in (emit,)]
    o_arg = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
    if o_arg: a = [x for x in a if x != o_arg]
    lvl = a[0]; notoon = a[1] if len(a) > 1 else None
    flat = str(Path(lvl).with_name('flat912.bin')); out = str(Path(lvl).with_name('marks912.bin'))
    if emit == 'flat': flat = o_arg
    elif emit == 'marks': out = o_arg
    f, tex, sig = F.load_level(lvl); ntex = len(tex)
    fb = bytearray(F.build(lvl, notoon)[0]); assert fb[:4] == b'FLT1' and struct.unpack_from('<I', fb, 4)[0] == ntex
    ntex_, npc = struct.unpack_from('<II', f, 4); ptab = struct.unpack_from('<I', f, 76)[0]; ncell, ctab = struct.unpack_from('<II', f, 80)
    cells = [struct.unpack_from('<6fIIIII', f, ctab + 48 * i) for i in range(ncell)]
    recs = [struct.unpack_from('<6fiIIII3ffIII2I', f, ptab + 80 * i) for i in range(npc)]
    # пригодность: все куски текстуры — непрозрачные куски города
    bad = set()
    for r in recs:
        t, fl, own = r[6], r[7], r[10]
        if 0 <= t < ntex and (own != 0 or fl & (1 | 2 | 4 | (1 << 24))): bad.add(t)
    cand = {}
    for i, t in enumerate(tex):
        if not t['ground'] or fb[12 + 8 * i] == 1 or i in bad: continue
        r = analyse_texture(f, t)
        if r: cand[i] = r
    print('кандидатов (текстур с разметкой):', {i: (c['n'], round(c['share'], 3), len(c['classes'])) for i, c in cand.items()})
    DEDUP = set()
    verts = collections.defaultdict(list)   # клетка -> список вершин (pos, свет RGB, цвет разметки RGB)
    ntri = collections.Counter(); nquad = collections.Counter(); nfrag = collections.Counter()
    # 1) треугольники кандидатов по текстурам: мир, UV, свет, клетка
    tris = collections.defaultdict(list)
    for r in recs:
        t, fl, own, ni = r[6], r[7], r[10], r[9]
        if t not in cand or own != 0 or ni <= 0 or not (fl & 16): continue
        vs = 12 if fl & 32 else 16; ox, oy, oz, sc = r[11:15]; off, nf, ci = r[15:18]
        base = cells[ci][9] + off
        raw = np.frombuffer(f, np.uint8, ni * vs, base).reshape(ni, vs)
        uv = raw[:, 0:4].copy().view('<u2').reshape(ni, 2).astype(float) / 256.0
        xyz = (raw[:, 6:12] if vs == 12 else raw[:, 8:14]).copy().view('<i2').reshape(ni, 3).astype(float) * (sc / 32768.0) + np.array([ox, oy, oz])
        col = decode_color(raw, vs)
        for k in range(0, ni - 2, 3): tris[t].append((ci, uv[k:k + 3], xyz[k:k + 3], col[k:k + 3]))
    for t, tl in tris.items():
        c = cand[t]; W, H = c['w'], c['h']
        # 2) классы: одинаковое отображение UV -> мир (A, B) и сдвиг решётки по целым повторам
        classes = []   # dict(A,B,O,tris=[(ci, tu', P, C, inv)])
        for (ci, tu, P, C) in tl:
            M = np.array([[tu[1][0] - tu[0][0], tu[2][0] - tu[0][0]], [tu[1][1] - tu[0][1], tu[2][1] - tu[0][1]]])
            if abs(np.linalg.det(M)) < 1e-9: continue
            Mi = np.linalg.inv(M); E = np.stack([P[1] - P[0], P[2] - P[0]])   # 2x3
            AB = Mi.T @ E if False else (np.linalg.inv(M.T) @ E)               # строки: A, B (мир на единицу u и v)
            A, B = AB[0], AB[1]; O = P[0] - tu[0][0] * A - tu[0][1] * B
            placed = None
            for cl in classes:
                if np.abs(cl['A'] - A).max() > CLS_TOL or np.abs(cl['B'] - B).max() > CLS_TOL: continue
                d = O - cl['O']; ij, *_ = np.linalg.lstsq(np.stack([A, B], axis=1), d, rcond=None)
                if np.abs(ij - np.rint(ij)).max() < 0.05 and np.abs(np.stack([A, B], axis=1) @ ij - d).max() < 0.05: placed = (cl, np.rint(ij)); break
            if placed is None:
                cl = dict(A=A, B=B, O=O, T=[]); classes.append(cl); shift = np.zeros(2)
            else: cl, shift = placed
            cl['T'].append((ci, tu + shift, P, C, np.linalg.inv(M), tu[0] + shift))
        if DEBUG: print('  текстура', t, 'треугольников', len(tl), 'классов', len(classes), sorted((len(x['T']) for x in classes), reverse=True)[:8])
        for cl in classes:
            T = cl['T']; A, B, O = cl['A'], cl['B'], cl['O']
            allu = np.concatenate([x[1] for x in T]); u_lo, v_lo = np.floor(allu.min(axis=0)).astype(int); u_hi, v_hi = np.ceil(allu.max(axis=0)).astype(int)
            if (u_hi - u_lo) * (v_hi - v_lo) > 3000: continue
            # сетка треугольников в UV (шаг 0,25)
            G = collections.defaultdict(list)
            for n, x in enumerate(T):
                tu = x[1]
                for gu in range(int(np.floor(tu[:, 0].min() * 4)), int(np.floor(tu[:, 0].max() * 4)) + 1):
                    for gv in range(int(np.floor(tu[:, 1].min() * 4)), int(np.floor(tu[:, 1].max() * 4)) + 1): G[(gu, gv)].append(n)
            def find(u, v):
                for n in G.get((int(np.floor(u * 4)), int(np.floor(v * 4))), ()):
                    ci, tu, P, C, inv, u0 = T[n]
                    lam = inv @ np.array([u - u0[0], v - u0[1]]); w = np.array([1 - lam[0] - lam[1], lam[0], lam[1]])
                    if (w >= -1e-6).all(): return n, w
                return None, None
            def cand_tris(ru):
                out = set()
                for gu in range(int(np.floor(ru[0] * 4)), int(np.floor(ru[2] * 4)) + 1):
                    for gv in range(int(np.floor(ru[1] * 4)), int(np.floor(ru[3] * 4)) + 1): out.update(G.get((gu, gv), ()))
                return out
            for ci_cls, rects in enumerate(c['rects']):
                mc = c['classes'][ci_cls]
                for iu in range(u_lo, u_hi):
                    for iv in range(v_lo, v_hi):
                        for (x0, y0, x1, y1) in rects:
                            ru = (iu + x0 / W, iv + y0 / H, iu + x1 / W, iv + y1 / H)
                            small = (np.linalg.norm(A) * (ru[2] - ru[0])) * (np.linalg.norm(B) * (ru[3] - ru[1])) < SMALL_AREA
                            cands = cand_tris(ru)
                            if not cands: continue
                            # доля штриха внутри дороги этого класса: сетка 5x5 точек
                            inside = 0
                            for a_ in range(5):
                                for b_ in range(5):
                                    n, _w = find(ru[0] + (ru[2] - ru[0]) * (a_ + .5) / 5, ru[1] + (ru[3] - ru[1]) * (b_ + .5) / 5)
                                    inside += n is not None
                            if inside == 0: continue
                            if inside >= (0.55 if small else 0.7) * 25:   # штрих (почти) целиком на дороге — одним четырёхугольником, без нарезки по швам (недолёт/перелёт до 30 % длины)
                                n, w = find((ru[0] + ru[2]) / 2, (ru[1] + ru[3]) / 2)
                                if n is None: n = next(iter(cands))
                                wc = O + ((ru[0] + ru[2]) / 2) * A + ((ru[1] + ru[3]) / 2) * B
                                key = (int(round(wc[0] / 0.15)), int(round(wc[1] / 0.15)), int(round(wc[2] / 0.15)), ci_cls, id(c))
                                if key in DEDUP: continue
                                DEDUP.add(key)
                                ci, tu, P, C, inv, u0 = T[n]; cb = cells[ci]; org = np.array([(cb[0] + cb[3]) * .5, 0.0, (cb[2] + cb[5]) * .5])
                                pts = []
                                for q in ((ru[0], ru[1]), (ru[2], ru[1]), (ru[2], ru[3]), (ru[0], ru[3])):
                                    lam = inv @ np.array([q[0] - u0[0], q[1] - u0[1]]); wq = np.array([1 - lam[0] - lam[1], lam[0], lam[1]])
                                    pts.append((O + q[0] * A + q[1] * B - org, np.clip(wq @ C, 0, 255)))
                                for tri_ in ((0, 1, 2), (0, 2, 3)):
                                    for j_ in tri_: verts[ci].append((pts[j_][0], pts[j_][1], mc, small))
                                    ntri[t] += 1
                                nquad[t] += 1
                                continue
                            nfrag[t] += 1   # штрих заходит за край дороги или на шов с другим отображением: куски по треугольникам этого класса
                            for n in cands:
                                ci, tu, P, C, inv, u0 = T[n]
                                if ru[2] < tu[:, 0].min() or ru[0] > tu[:, 0].max() or ru[3] < tu[:, 1].min() or ru[1] > tu[:, 1].max(): continue
                                poly = tri_poly(ru, tu)
                                if len(poly) < 3: continue
                                ar = 0.5 * abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly))))
                                if ar < SLIVER * (ru[2] - ru[0]) * (ru[3] - ru[1]): continue   # крошка штриха на шве: не видна, а треугольников стоит
                                cb = cells[ci]; org = np.array([(cb[0] + cb[3]) * .5, 0.0, (cb[2] + cb[5]) * .5]); pts = []
                                for (pu, pv) in poly:
                                    lam = inv @ np.array([pu - u0[0], pv - u0[1]]); w = np.array([1 - lam[0] - lam[1], lam[0], lam[1]])
                                    pts.append((O + pu * A + pv * B - org, np.clip(w @ C, 0, 255)))
                                for j in range(1, len(pts) - 1):
                                    for q in (pts[0], pts[j], pts[j + 1]): verts[ci].append((q[0], q[1], mc, small))
                                    ntri[t] += 1
    # запись: положение — в осях кусков клетки (как матрица модели движка: sc/32768 · число + (ox, oy, oz)), класс цвета разметки — по общей таблице уровня (до 16 цветов)
    frame = {}
    for r in recs:
        if r[10] != 0 or r[9] <= 0 or r[7] & 1 << 26 or ((r[7] & 2) and not (r[7] & 4)): continue   # куски листа клетки: непрозрачные куски города
        ci = r[17]; fr = (r[11], r[12], r[13], r[14])
        if ci not in frame: frame[ci] = fr
        elif frame[ci] is not None and max(abs(a - b) for a, b in zip(frame[ci], fr)) > 1e-4: frame[ci] = None   # у кусков клетки разные оси — клетка без разметки
    table_cols = []
    for c in cand.values():
        for col in c['classes']:
            col = tuple(int(x) for x in col)
            if col not in table_cols: table_cols.append(col)
    assert len(table_cols) <= 16, 'цветов разметки больше 16'
    body = bytearray(); table = []; nv = 0; skipped = 0
    for ci in range(ncell):
        vv = verts.get(ci, []); fr = frame.get(ci)
        if fr is None: vv = []; skipped += 1 if verts.get(ci) else 0
        vv = [v for v in vv if not v[3]] + [v for v in vv if v[3]]   # сначала крупная разметка, затем мелочь
        nbig = sum(1 for v in vv if not v[3]); table.append((nv, nbig, len(vv) - nbig))
        cb = cells[ci]; org = np.array([(cb[0] + cb[3]) * .5, 0.0, (cb[2] + cb[5]) * .5])
        for pos, lc, mc, _sm in vv:
            m = (pos + org - np.array(fr[:3])) / (fr[3] / 32768.0)
            p_ = np.clip(np.rint(m), -32768, 32767).astype('<i2'); k = table_cols.index(tuple(int(x) for x in mc))
            body += p_.tobytes() + bytes(int(x) for x in np.rint(lc)) + bytes([k, 0, 0]); nv += 1
    hdr = b'MRK2' + struct.pack('<IIII', ntex, sig, ncell, len(table_cols)) + b''.join(struct.pack('<III', a_, b_, c_) for a_, b_, c_ in table) + b''.join(bytes(c) + b'\0' for c in table_cols)
    if emit != 'flat': Path(out).write_bytes(hdr + bytes(body))
    for i in cand:
        if ntri[i]: fb[12 + 8 * i] = 3; fb[12 + 8 * i + 1] = 0; fb[12 + 8 * i + 2: 12 + 8 * i + 5] = bytes(int(x) for x in np.rint(cand[i]['base'])); fb[12 + 8 * i + 5] = 255
    if emit != 'marks': Path(flat).write_bytes(bytes(fb))
    print('клеток с разными осями кусков (без разметки):', sum(1 for v in frame.values() if v is None))
    print(f'{lvl}: разметка: текстур {len(cand)}, треугольников {sum(ntri.values())}, вершин {nv}, клеток с разметкой {sum(1 for t in table if t[1] or t[2])}, мелочи {sum(t[2] for t in table)} вершин из {nv}, файл {len(hdr) + len(body)} байт -> {out}')
    print('треугольников по текстурам:', dict(ntri), ' целых прямоугольников', dict(nquad), ' штрихов нарезкой', dict(nfrag))


if __name__ == '__main__':
    main()
