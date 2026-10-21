#!/usr/bin/env python3
"""Плоские нарисованные детали (вывески, коврики, наклейки, разметка) и вообще все треугольники диска — целы ли они
в собранном уровне и комнатах (правка Роба 43, 28.09: «SCHOOL будто срезан треугольником, коврик Welcome поломан,
и вот так всё»).

    python tools/decals.py [build/level.shr] [--rooms build/interiors-l1-gfx.bin] [--plant uv|drop|face] [--no-src]

Проверки:
  A  текстура на треугольнике (город ближн./дальн., машина, небо, комнаты): размах UV так, как их читает GE (u16,
     tools/uvq.py), не больше SPAN_MAX повторов. Больше бывает только от перескока знака: треугольник рисуется плоским
     средним цветом — причина семейства 43 (половина вывески школы, клин на коврике, пятна дороги и травы).
  B  ни один треугольник диска не потерян: исходные треугольники города (Converter hit-and-run-web по сценам уровня, как
     tools/psp_export.py main) против ближней версии кусков — площадь экспортированных треугольников в плоскости каждого
     исходного (центр внутри, зазор < 5 мм, параллельно, текстура ложится так же) не меньше COVER_MIN его площади.
     Судим объекты (экземпляры мешей), которые стоят в городе «как есть» — совпала хотя бы половина их площади; пропы,
     стейтпропы, анимированные объекты (своя поза кадра 0) и небо рисуются своими секциями и не в счёт.
     Отдельно — семейство «наклеек» (исходный треугольник лежит на другой поверхности или перед ней ближе DECAL_GAP,
     параллельно, и меньше её): сколько их всего, сколько с перескоком UV и сколько потеряно.
  C  обход (сводка): город рисуется без отсечения (O_CULL выкл. в viewer/main.c), кроме слоёв со стороной (флаг 512,
     tools/psp_export.py mark_layers, правки 37/43 от 29.09) — их обход развёрнут лицом от подложки, движок отсекает
     изнанку. Считается, сколько наклеек в кусках с отсечением смотрят на свою исходную подложку (у неровных наклеек
     разные куски лежат над разными подложками — сторону каждого треугольника судит D по его соседям в файле) и сколько
     в кусках без отсечения и без флага 8 смотрят на подложку (обход там не виден; до 29.09 это была вся проверка C).
  D  семейство целиком: каждая исходная наклейка (с 29.09 полупрозрачное — наклейка над непрозрачным, как в экспорте)
     цела (A, B) и стоит ровно по правилу глубины движка (tools/seams.py layers: не мигает с подложкой, не спрятана под
     ней, не просвечивает сквозь неё; наклейка в плоскости подложки — со сдвигом выше её). Провал: UV/потери — хоть одна;
     по глубине — площадь плохих треугольников наклеек больше допуска tools/seams.py (1%, не меньше 2 м²).
--plant: заведомо плохой вход на копии файла (гейт обязан упасть): uv — у треугольника вывески школы старая запись
со знаком (u = −1/256 у одной вершины); drop — этот треугольник вырожден (потерян); face — у слоёв со стороной на
коврике Welcome обход развёрнут к подложке (ловит место «коврик Welcome»). Код выхода 1 — провал."""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[1]/"tools"))
from main_source import read_main
import argparse, json, os, re, struct, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import shr7read, coplanar   # noqa: E402

SPAN_MAX = 128.0      # повторов текстуры на один треугольник (данные уровня 1: до 41; перескок знака даёт ~256)
# места из жалоб Роба (правки 37/43, видео 28.09) — здесь допуска нет: ни одного плохого треугольника наклейки в SPOT_R м
SPOTS = (('вывеска SCHOOL', (-34.3, 8.9, 589.6)), ('коврик Welcome', (228.9, 3.9, 183.3)),
         ('вывеска Kwik-E-Mart', (205.5, 10.9, 306.6)), ('тень дерева у дома', (209.5, 3.6, 203.2)))
SPOT_R = 4.0
DECAL_GAP = 0.5       # м: деталь на поверхности или перед ней (вывеска школы — 0.19 м перед стеной, коврик — 7 см над полом)
COVER_MIN = 0.9      # доля площади; решётка и сварка швов (правка 37) меняют площадь мелких треугольников на проценты
AREA_MIN = 0.02       # м²: судим треугольники от 2 дм² (мельче — шум квантования вершин, глазом не видно)
PLANE_EPS = 0.005
IN_EPS = 0.003        # м: запас «центр внутри исходного треугольника»     # м: экспортированный треугольник в плоскости исходного (квантование вершин куска ≤ 0.6 мм)
F_DOUBLE = 8
SRC_BLEND = SRC_SUB = None   # заполняют source_city и decal_src
F_LSIDE = 512   # слой со стороной (tools/psp_export.py mark_layers): движок рисует его с отсечением изнанки


def tri_area(P):
    return np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) / 2


def o_cull_on():
    s = read_main(ROOT / 'viewer/main.c', errors="replace")
    m = re.search(r'#define O_DEFAULT \(([^)]*)\)', s)
    return bool(m and 'O_CULL' in m.group(1))


# ---------------------------------------------------------------------------------------- исходные треугольники диска
def source_city(level=1):
    """-> P (N,3,3) мир как у экспорта, UV (N,3,2), OBJ (N,) номер экземпляра, NAME [имя экземпляра], TEX [имя текстуры]"""
    os.environ.setdefault('SHR_TMP', tempfile.mkdtemp(prefix='decals_conv_'))
    import convert
    convert.OUT = Path(os.environ['SHR_TMP']); convert.OUT.mkdir(parents=True, exist_ok=True)
    from p3d import read
    art = convert.GAME / 'art'
    scenes = [f'l{level}_terra'] + sorted(p.stem for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
    conv = convert.Converter()
    for path in sorted(art.glob(f'l{level}*.p3d')):
        try: conv.resources(read(path))
        except Exception: pass
    P, UV, OBJ, names, texs = [], [], [], [], []
    global SRC_BLEND
    blend = []
    import io, contextlib
    for scene in scenes:
        with contextlib.redirect_stdout(io.StringIO()): conv.export(art / f'{scene}.p3d', f'dc_{scene}')
        meta = json.loads((convert.OUT / f'dc_{scene}.json').read_text()); raw = (convert.OUT / f'dc_{scene}.bin').read_bytes()
        for ext in ('json', 'bin'): (convert.OUT / f'dc_{scene}.{ext}').unlink()
        for obj in meta['objects']:
            if obj['name'].lower().startswith(('horizon', 'sky')) or obj['mesh'] == 'Plane1Shape': continue
            M = np.array(obj['matrix'], np.float64).reshape(4, 4); oi = len(names); names.append(f"{scene}/{obj['name']}")
            for prim in meta['meshes'].get(obj['mesh'], []):
                at = prim['attributes']
                pos = np.frombuffer(raw, '<f4', at['position'][1], at['position'][0]).reshape(-1, 3)
                idx = np.frombuffer(raw, '<u4', at['indices'][1], at['indices'][0])
                uv = np.frombuffer(raw, '<f4', at['uv'][1], at['uv'][0]).reshape(-1, 2)
                w = (np.c_[pos, np.ones(len(pos))] @ M)[:, :3][idx].reshape(-1, 3, 3)
                P.append(w); UV.append(uv[idx].reshape(-1, 3, 2).astype(np.float64)); OBJ.append(np.full(len(w), oi))
                mat = meta['materials'].get(prim['shader'], {})
                texs.extend([mat.get('texture', '')] * len(w))
                blend.extend([bool(mat.get('translucent') or mat.get('blend')) and not mat.get('alpha')] * len(w))   # смешивание без вырезки: глубину не пишет
    SRC_BLEND = np.array(blend, bool)
    return np.concatenate(P), np.concatenate(UV), np.concatenate(OBJ), names, texs


def match(S, E, SUV=None, EUV=None, cell=4.0):
    """для каждого экспортированного треугольника E — исходный треугольник S, в плоскости которого лежит его центр
    (внутри, зазор < PLANE_EPS, параллельно) и чья текстура ложится так же (UV вершин E = UV S в этих точках с точностью
    до целого повтора и 2/256): -> пары (e, s)"""
    nS = np.cross(S[:, 1] - S[:, 0], S[:, 2] - S[:, 0]); aS = np.linalg.norm(nS, axis=1); ok = aS > 1e-9
    nS[ok] /= aS[ok, None]
    nE = np.cross(E[:, 1] - E[:, 0], E[:, 2] - E[:, 0]); aE = np.linalg.norm(nE, axis=1); okE = aE > 1e-9
    nE[okE] /= aE[okE, None]
    cE = E.mean(1)
    si = np.nonzero(ok)[0]
    mg = PLANE_EPS + .01   # запас: центр экспортированного треугольника на границе клетки (квантование вершин куска)
    lo = np.floor((S[si].min(1)[:, [0, 2]] - mg) / cell).astype(np.int64); hi = np.floor((S[si].max(1)[:, [0, 2]] + mg) / cell).astype(np.int64)
    span = hi - lo + 1; cnt = span[:, 0] * span[:, 1]
    rep = np.repeat(np.arange(len(si)), cnt); k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    gx = lo[rep, 0] + k % span[rep, 0]; gz = lo[rep, 1] + k // span[rep, 0]
    key = (gx + 100000) * 200000 + (gz + 100000); o = np.argsort(key, kind='stable'); key, sj = key[o], si[rep[o]]
    ce = np.floor(cE[:, [0, 2]] / cell).astype(np.int64); ekey = (ce[:, 0] + 100000) * 200000 + (ce[:, 1] + 100000)
    a, b = np.searchsorted(key, ekey, 'left'), np.searchsorted(key, ekey, 'right')
    out_e, out_s = [], []
    ei = np.nonzero(okE)[0]
    for c0 in range(0, len(ei), 50000):
        e = ei[c0:c0 + 50000]; m = b[e] - a[e]
        E_ = np.repeat(e, m); S_ = sj[np.repeat(a[e], m) + (np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m))]
        d = np.einsum('ij,ij->i', nE[E_], nS[S_]); sel = np.abs(d) > .98; E_, S_ = E_[sel], S_[sel]   # мелкие дети тонких «лент» после решётки наклонены до ~10°
        g = np.einsum('ij,ij->i', cE[E_] - S[S_, 0], nS[S_]); sel = np.abs(g) < PLANE_EPS; E_, S_, g = E_[sel], S_[sel], g[sel]
        q = cE[E_] - g[:, None] * nS[S_]
        v0, v1, v2 = S[S_, 1] - S[S_, 0], S[S_, 2] - S[S_, 0], q - S[S_, 0]
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1); d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01; den[den == 0] = 1e-12
        u = (d11 * d20 - d01 * d21) / den; v = (d00 * d21 - d01 * d20) / den
        # центр внутри S с запасом IN_EPS по расстоянию до рёбер (сдвиг вершин решёткой и сваркой — у тонких «лент»
        # центр детей у острого конца выходит за ребро на миллиметры)
        sel = np.ones(len(E_), bool)
        for i0, i1 in ((0, 1), (1, 2), (2, 0)):
            a0, a1 = S[S_, i0], S[S_, i1]; ed = a1 - a0; inw = np.cross(nS[S_], ed); inw /= np.maximum(np.linalg.norm(inw, axis=1, keepdims=True), 1e-12)
            sel &= ((q - a0) * inw).sum(1) >= -IN_EPS
        E_, S_ = E_[sel], S_[sel]
        if SUV is not None:   # UV вершин E в барицентрике S (плоскость S, мир)
            den_, ok_ = den[sel], np.ones(len(E_), bool)
            # допуск: 2.5/256 записи UV + сдвиг вершин (решётка ≤ 1 мм + сварка швов ≤ 1.2 мм, берём 5 мм) × градиент UV
            # исходного треугольника (у длинных тонких «лент» UV меняется на сантиметрах поперёк)
            e1_, e2_ = SUV[S_, 1] - SUV[S_, 0], SUV[S_, 2] - SUV[S_, 0]
            hmin = 2 * np.sqrt(den_) / np.maximum(np.sqrt(np.maximum(d00[sel], d11[sel])), 1e-9)   # высота треугольника S
            grad = np.maximum(np.abs(e1_).max(1), np.abs(e2_).max(1)) / np.maximum(hmin, 1e-6)
            tol = 2.5 / 256 + grad * .005
            for j in range(3):
                w2 = E[E_, j] - S[S_, 0]
                d20, d21 = (w2 * v0[sel]).sum(1), (w2 * v1[sel]).sum(1)
                bu = (d11[sel] * d20 - d01[sel] * d21) / den_; bv = (d00[sel] * d21 - d01[sel] * d20) / den_
                uvS = SUV[S_, 0] * (1 - bu - bv)[:, None] + SUV[S_, 1] * bu[:, None] + SUV[S_, 2] * bv[:, None]
                dd = EUV[E_, j] - uvS; dd -= np.round(dd)
                ok_ &= (np.abs(dd) < tol[:, None]).all(1)
            E_, S_ = E_[ok_], S_[ok_]
        out_e.append(E_); out_s.append(S_)
    return np.concatenate(out_e), np.concatenate(out_s)


def decal_src(S):
    """исходные треугольники-наклейки: на другой поверхности / перед ней ближе DECAL_GAP, параллельно и меньше её
    -> (маска, OUT (N,3): единичный вектор от поверхности-подложки к наклейке — сторона, с которой наклейку видно;
    нули, если наклейка лежит в самой плоскости подложки, ближе 2 мм — там сторону решает сама подложка)"""
    z = np.zeros(len(S), int)
    R, N, C, A = coplanar.analyze(S, z, z, np.arange(len(S)), maxgap=DECAL_GAP)
    ai, bj, g = R[:, 0].astype(int), R[:, 1].astype(int), R[:, 2]
    bl = SRC_BLEND if SRC_BLEND is not None and len(SRC_BLEND) == len(S) else np.zeros(len(S), bool)
    sel = ((A[ai] < A[bj] * .999) | bl[ai]) & ~bl[bj]   # тень/стекло — наклейка над непрозрачным, не подложка
    ai, bj, g = ai[sel], bj[sel], g[sel]
    m = np.zeros(len(S), bool); m[ai] = True
    o = np.lexsort((np.abs(g), ai)); ai, bj, g = ai[o], bj[o], g[o]; first = np.r_[True, ai[1:] != ai[:-1]]
    ai, bj, g = ai[first], bj[first], g[first]
    out = np.zeros((len(S), 3)); far_ = np.abs(g) >= .002
    out[ai[far_]] = np.sign(g[far_])[:, None] * N[bj[far_]]
    global SRC_SUB
    SRC_SUB = np.full((len(S), 2), np.nan); SRC_SUB[ai, 0] = bj; SRC_SUB[ai, 1] = g   # подложка и зазор (для C)
    return m, out


# ---------------------------------------------------------------------------------------------------- проверки
def check_span(name, d, fails, notes):
    if not len(d['P']): return np.zeros(0, bool)
    span = (d['UV'].max(1) - d['UV'].min(1)).max(1); ar = tri_area(d['P'])
    bad = (span > SPAN_MAX) & (ar >= AREA_MIN)   # крошки < 2 дм² с размахом UV в сотни повторов бывают на самом диске (скейт в доме: 100…1100)
    notes.append(f"A {name}: треуг. {len(span):,}; с перескоком UV (размах > {SPAN_MAX:g} повторов — плоский цвет) {int(bad.sum()):,} "
                 f"({ar[bad].sum():,.0f} м² из {ar.sum():,.0f}), кусков {len(np.unique(d['PI'][bad]))}")
    if bad.any():
        i = int(np.nonzero(bad)[0][np.argmax(ar[bad])]); c = d['P'][i].mean(0)
        fails.append(f"A {name}: {int(bad.sum()):,} треуг. рисуются плоским цветом (UV перескакивают через 0; крупнейший у "
                     f"({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}), размах {span[i]:.0f} повторов)")
    return bad


def check_src(d, bad_uv, fails, notes, cull):
    S, SUV, OBJ, names, texs = source_city()
    aS = tri_area(S); E = d['P']
    emax = np.max([np.linalg.norm(S[:, (k + 1) % 3] - S[:, k], axis=1) for k in range(3)], 0)
    keep = (aS >= AREA_MIN) & (2 * aS / np.maximum(emax, 1e-9) > 1e-3)   # без крошек и вырожденных «иголок» (высота < 1 мм)
    e, s = match(S, E, SUV, d['UV'])
    cov = np.bincount(s, weights=tri_area(E)[e], minlength=len(S)) / np.maximum(aS, 1e-12)
    # объект в городе «как есть» — совпала хотя бы половина его площади; остальные (пропы, стейтпропы, анимированные
    # объекты в своей позе кадра 0, небо) рисуются своими секциями и здесь не в счёт
    oa = np.bincount(OBJ, weights=aS * keep, minlength=len(names)); om = np.bincount(OBJ, weights=aS * keep * np.minimum(cov, 1), minlength=len(names))
    present_obj = om >= .5 * np.maximum(oa, 1e-12)
    judged = keep & present_obj[OBJ]
    lost = judged & (cov < COVER_MIN)
    dec, side = decal_src(S); dec &= judged
    # наклейки с перескоком UV: хоть одна часть исходного треугольника с перескоком
    buv = np.zeros(len(S), bool); buv[s[bad_uv[e]]] = True
    notes.append(f"B город: исходных треуг. {len(S):,} (объектов в городе {int(present_obj.sum()):,} из {len(names):,}); "
                 f"потеряно {int(lost.sum()):,} ({aS[lost].sum():.1f} м²)")
    notes.append(f"B наклейки (на поверхности или перед ней ≤ {DECAL_GAP:g} м): {int(dec.sum()):,} исходных треуг. "
                 f"({aS[dec].sum():,.0f} м²), с перескоком UV {int((dec & buv).sum()):,}, потеряно {int((dec & lost).sum()):,}")
    if lost.any():
        i = int(np.nonzero(lost)[0][np.argmax(aS[lost])]); c = S[i].mean(0)
        fails.append(f"B город: потеряно {int(lost.sum()):,} исходных треуг.; крупнейший {aS[i]:.2f} м² у ({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}) "
                     f"({names[OBJ[i]]}, {texs[i]}), покрыт на {cov[i] * 100:.0f}%")
    # C: наклейка перед подложкой в куске, который движок рисует с отсечением (слой со стороной, флаг 512, или весь город
    # при O_CULL без флага 8), обязана смотреть лицом ОТ подложки — иначе со своей стороны её не видно («спрятана»).
    # Лицо = CCW, нормаль (b−a)×(c−a), как tools/wind.c и sceGuFrontFace(GU_CCW). В кусках без отсечения обход не виден
    nE = np.cross(E[:, 1] - E[:, 0], E[:, 2] - E[:, 0])
    culled = ((d['FL'][e] & F_LSIDE) != 0) | (cull & ((d['FL'][e] & F_DOUBLE) == 0))
    # подложка, которую видит и экспорт: пишет глубину и ближе окна слоёв (tools/seams.py SAND_GAP), наклейка не «бутерброд»
    import seams
    sb = SRC_SUB[:, 0]; hasb = ~np.isnan(sb); sbi = np.where(hasb, sb, 0).astype(int)
    real = hasb & ~SRC_BLEND[sbi] & (cov[sbi] >= COVER_MIN) & (np.abs(np.nan_to_num(SRC_SUB[:, 1])) < seams.SAND_GAP)   # подложка сама стоит в городе (не проп, не стейтпроп)
    inward = culled & dec[s] & real[s] & (np.einsum('ij,ij->i', nE[e], side[s]) < 0)
    wrong = np.zeros(len(S), bool); wrong[s[inward]] = True
    loose = ~culled & dec[s] & (np.einsum('ij,ij->i', nE[e], side[s]) < 0) & ((d['FL'][e] & F_DOUBLE) == 0)
    lw = np.zeros(len(S), bool); lw[s[loose]] = True
    notes.append(f"C обход: наклеек лицом к подложке в кусках с отсечением (слой со стороной 512{', O_CULL' if cull else ''}): "
                 f"{int(wrong.sum()):,} исходных треуг.; в кусках без отсечения и без флага 8 (обход не виден, сводка): {int(lw.sum()):,}")
    # D: семейство целиком — каждая исходная наклейка цела (UV, не потеряна) и стоит ровно: её треугольники в файле не
    # мигают с подложкой, не спрятаны под ней и не просвечивают сквозь неё (правило глубины движка — tools/seams.py)
    import seams
    eng = seams.engine(); K = seams.depth_k(eng['near'], eng['far'])
    L = seams.layers(d, K, seams.D_CITY, eng['bias'], eng['cull'])
    fam = {}
    for nm in ('мигает', 'спрятана', 'просвечивает'):
        t_ = np.zeros(len(S), bool); t_[s[L[nm][e]]] = True; fam[nm] = dec & t_
    # наклейка в самой плоскости подложки (< 2 мм, стороны нет): сверху обязана быть наклейка — у её треугольников в файле
    # сдвиг больше, чем у треугольников её подложки под ними (иначе картинку наклейки закрывает подложка). Другая текстура
    FLe = d['FL']; lev = np.where(FLe & 64, 1 + ((FLe & 256) != 0) + 2 * ((FLe & 1024) != 0), 0)
    src_of = np.full(len(E), -1); src_of[e] = s
    Rc, _, _, _ = coplanar.analyze(E, d['TEX'], FLe & 7, d['PI'], maxgap=seams.COPLAN)
    x, y = Rc[:, 0].astype(int), Rc[:, 1].astype(int); sx, sy = src_of[x], src_of[y]
    ok2 = (sx >= 0) & (sy >= 0)
    x, y, sx, sy = x[ok2], y[ok2], sx[ok2], sy[ok2]
    subx = np.nan_to_num(SRC_SUB[sx, 0], nan=-1).astype(int); suby = np.nan_to_num(SRC_SUB[sy, 0], nan=-1).astype(int)
    difft = np.array([texs[a_] != texs[b_] for a_, b_ in zip(sx, sy)], bool)
    under = difft & (((subx == sy) & dec[sx] & (lev[x] <= lev[y])) | ((suby == sx) & dec[sy] & (lev[y] <= lev[x])))
    und = np.zeros(len(S), bool); und[np.where(subx == sy, sx, sy)[under]] = True; fam['под подложкой'] = dec & und
    bad = dec & (buv | lost | fam['мигает'] | fam['спрятана'] | fam['просвечивает'] | fam['под подложкой'])
    ok_ = dec & ~bad
    # провал по глубине — как у tools/seams.py: площадь плохих треугольников наклеек в файле больше допуска (1% площади
    # треугольников наклеек, не меньше 2 м²): остаток сложных стопок, которые общее правило экспорта не разводит
    ed = dec[s]; badE = np.zeros(len(E), bool)
    for nm in ('мигает', 'спрятана', 'просвечивает'): badE |= L[nm]
    badE[np.r_[x[under & (subx == sy)], y[under & (suby == sx)]]] = True
    aE = tri_area(E); fam_e = np.zeros(len(E), bool); fam_e[e[ed]] = True
    b_area, f_area = float(aE[badE & fam_e].sum()), float(aE[fam_e].sum())
    budget = max(seams.BUDGET_REL * f_area, seams.BUDGET_MIN)
    notes.append(f"D семейство наклеек: {int(dec.sum()):,} исходных треуг. ({aS[dec].sum():,.0f} м²) — целы и стоят ровно "
                 f"{int(ok_.sum()):,} ({aS[ok_].sum():,.0f} м²); мигают {int(fam['мигает'].sum()):,}, спрятаны {int(fam['спрятана'].sum()):,}, "
                 f"просвечивают {int(fam['просвечивает'].sum()):,}, под подложкой {int(fam['под подложкой'].sum()):,}, UV {int((dec & buv).sum()):,}, потеряны {int((dec & lost).sum()):,}")
    notes.append(f"D по глубине: плохих треугольников наклеек в файле {b_area:,.1f} м² из {f_area:,.0f} м² "
                 f"({100 * b_area / max(f_area, 1e-9):.2f}%), допуск {budget:,.1f} м²")
    if b_area > budget:
        nm = max(('мигает', 'спрятана', 'просвечивает', 'под подложкой'), key=lambda k: int(fam[k].sum())); m = fam[nm]
        i = int(np.nonzero(m)[0][np.argmax(aS[m])]); c = S[i].mean(0)
        fails.append(f"D наклейки: {b_area:,.1f} м² плохих больше допуска {budget:,.1f} м² (больше всего «{nm}»: {int(m.sum()):,} "
                     f"исходных треуг.; крупнейшая у ({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}) ({names[OBJ[i]]}, {texs[i]}, {aS[i]:.2f} м²))")
    cE = E.mean(1); sp_notes = []
    for nm_, pt in SPOTS:
        near_ = fam_e & (np.linalg.norm(cE - np.array(pt), axis=1) < SPOT_R)
        nb = int((near_ & badE).sum()); sp_notes.append(f'{nm_} {int(near_.sum())} треуг. / плохих {nb}')
        if nb: fails.append(f'D место «{nm_}»: {nb} плохих треугольников наклеек (мигают/спрятаны/просвечивают) в {SPOT_R:g} м')
    notes.append('D места Роба (без допуска): ' + '; '.join(sp_notes))
    for nm, m in (('UV', dec & buv), ('потеряны', dec & lost)):
        if m.any(): fails.append(f"D наклейки: {nm} {int(m.sum()):,} исходных треуг.")
    return dict(dec=dec, ok=ok_, fam=fam, S=S, aS=aS, texs=texs)


def plant(path, kind):
    """копия файла с заведомо плохой наклейкой -> путь к копии. Наклейка — вывеска школы (текстура elementarySign),
    если её найти по месту нельзя — крупнейший треугольник-деталь города"""
    b = bytearray(Path(path).read_bytes()); d = shr7read.load(path)
    C = d['P'].mean(1); ar = tri_area(d['P'])
    cand = np.nonzero((np.abs(C[:, 0] + 34.21) < .05) & (C[:, 1] > 7.8) & (C[:, 1] < 10.7) & (np.abs(C[:, 2] - 589.4) < 3.2) & (ar > .3))[0]
    if not len(cand): cand = np.array([int(np.argmax(ar * (d['FL'] & F_DOUBLE == 0)))])
    t = int(cand[np.argmax(ar[cand])]); off, vs = int(d['OFF'][t]), int(d['VS'][t]); c = C[t]
    print(f"подложено ({kind}): треугольник у ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}), {ar[t]:.2f} м², кусок {d['PI'][t]}")
    if kind == 'uv':      # старая запись со знаком: у вершины 0 u = −1/256, у второй u = 1 (треугольник пересекает 0)
        struct.pack_into('<h', b, off, -1); struct.pack_into('<h', b, off + vs, 256)
    elif kind == 'face':  # слои со стороной (флаг 512) на коврике Welcome смотрят на подложку: отсечение прячет их
        m = ((d['FL'] & F_LSIDE) != 0) & (np.linalg.norm(C - np.array([228.9, 3.9, 183.3]), axis=1) < 1.5)
        if not m.any(): m = np.zeros(len(C), bool); m[int(np.argmax(ar * ((d['FL'] & F_LSIDE) != 0)))] = True
        for o_, v_ in zip(d['OFF'][m], d['VS'][m]):
            o_, v_ = int(o_), int(v_); x1 = bytes(b[o_ + v_:o_ + 2 * v_]); b[o_ + v_:o_ + 2 * v_] = b[o_ + 2 * v_:o_ + 3 * v_]; b[o_ + 2 * v_:o_ + 3 * v_] = x1
        print(f"  обход развёрнут у {int(m.sum())} треуг. слоёв со стороной (коврик Welcome у (228.9, 183.3))")
    elif kind == 'drop':  # вырожденный треугольник: все три вершины = первая
        b[off + vs:off + 2 * vs] = b[off:off + vs]; b[off + 2 * vs:off + 3 * vs] = b[off:off + vs]
    tmp = Path(tempfile.mkdtemp(prefix='decals_plant_')) / 'planted.shr'; tmp.write_bytes(bytes(b))
    return tmp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shr', nargs='?', default=str(ROOT / 'build/level.shr'))
    ap.add_argument('--rooms', default=None, help='interiors-l1-gfx.bin (по умолчанию рядом с уровнем, если есть)')
    ap.add_argument('--plant', choices=('uv', 'drop', 'face'))
    ap.add_argument('--no-src', action='store_true', help='без сверки с диском (только A)')
    a = ap.parse_args()
    shr = plant(a.shr, a.plant) if a.plant else Path(a.shr)
    rooms = Path(a.rooms) if a.rooms else Path(a.shr).with_name('interiors-l1-gfx.bin')
    fails, notes = [], []
    near = shr7read.load(shr)
    bad = check_span('город ближн.', near, fails, notes)
    check_span('город дальн.', shr7read.load(shr, far=True), fails, notes)
    check_span('машина', shr7read.load(shr, owner=1), fails, notes)
    check_span('небо', shr7read.load(shr, owner=2), fails, notes)
    if rooms.exists():
        for nm, d in shr7read.load_rooms(rooms).items(): check_span(f'комната {nm}', d, fails, notes)
    if not a.no_src: check_src(near, bad, fails, notes, o_cull_on())
    print('FAIL: ' + fails[0] if fails else 'PASS: плоские детали и все треугольники диска целы — UV без перескока, потерь нет; '
          'наклейки стоят ровно (места Роба — чисто, остальное — в допуске)')
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
