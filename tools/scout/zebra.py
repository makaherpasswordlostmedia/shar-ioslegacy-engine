#!/usr/bin/env python3
"""Бот-зебра (№875, Роб 23.10: «NPC-машины встают прямо на пешеходном переходе — тупо, недоработанно»; «это тоже ботом на ночь»).
Трафик тормозит передним бампером у конца полосы (viewer/traffic.c stopLine), а зебра и стоп-линия лежат внутри полосы перед перекрёстком.
Бот для конца каждой полосы (traffic.shr TRF1) ищет наклейки на дороге (куски города с флагом слоя F_LAYER 64, почти горизонтальные) в
12 м перед концом и в ширину полосы; зебра/стоп-линия — скопление наклеек одного куска шире полосы поперёк (≥ 2,5 м) и короче вдоль (≤ 6 м).
Отступ стоп-линии = задний край такой наклейки за концом полосы + 0,5 м (не больше 8 м). Только чтение данных уровня.

  python3 tools/scout/zebra.py LEVEL.shr TRAFFIC.shr OUT_PREFIX
-> OUT_PREFIX_stop875.bin ('STP1', u32 n, n × {u16 road, u16 lane, f32 отступ м}), OUT_PREFIX_zebra.tsv (каждый найденный конец полосы),
   OUT_PREFIX_zebra.png (карта сверху: полосы серым, концы с зеброй — красным)."""
import struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shr7read as R

F_LAYER = 64
ZBACK = 6.0   # плитка с зеброй ищется не дальше 6 м перед концом полосы (дальше — зебры соседних подходов и середины квартала)
AHEAD, BACK, ALONG_MAX, ACROSS_MIN, CAP, MARGIN = 2.0, 12.0, 6.0, 2.5, 8.0, 0.5


def lanes(trf):
    b = Path(trf).read_bytes()
    assert b[:4] == b'TRF1', 'не TRF1'
    nJ, oJ, nR, oR, nP, oP = struct.unpack_from('<6I', b, 12)
    pts = np.frombuffer(b, '<f4', nP * 4, oP).reshape(-1, 4)
    out = []
    for r in range(nR):
        sJ, eJ, rev, nl, fl, mc, sp, _, fp, npt, _, ln, wd, _ = struct.unpack_from('<4H4BIHHfff', b, oR + 32 * r)
        if fl & 2 or mc == 0 or npt < 2: continue
        for k in range(nl):
            P = pts[fp + k * npt: fp + (k + 1) * npt]
            out.append((r, k, P[-1, :3].astype(np.float64), (P[-1, :3] - P[-2, :3]).astype(np.float64), wd / max(nl, 1), P[:, [0, 2]]))
    return out


def stripe_rows(img):
    """Строки текстуры с полосами зебры: вдоль строки ≥ 6 смен «белое (> 190) / тёмное (< 130)». -> маска строк (или None)."""
    g = img[..., :3].astype(np.float32).mean(-1); hi, lo = np.percentile(g, 92), np.percentile(g, 40)
    if hi - lo < 45: return None   # без контраста полос нет (ночная палитра L7 темнее — пороги от самой текстуры)
    w, d = g > lo + (hi - lo) * .75, g < lo + (hi - lo) * .3
    lab = np.where(w, 1, np.where(d, -1, 0))
    rows = np.zeros(g.shape[0], bool)
    for r in range(g.shape[0]):
        x = lab[r][lab[r] != 0]
        rows[r] = len(x) > 4 and int((np.diff(x) != 0).sum()) >= 6
    return rows if rows.mean() >= .08 else None


def main():
    lv, trf, pre = sys.argv[1], sys.argv[2], sys.argv[3]
    import tex_gate as G
    bb = Path(lv).read_bytes(); trecs, _, _, _ = G.walk(bb)
    t = R.load(lv); P = t['P'].astype(np.float64); fl = t['FL']; pi = t['PI']; TX = t['TEX']; UV = t['UV'].astype(np.float64)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); ny = np.abs(n[:, 1]) / (np.linalg.norm(n, axis=1) + 1e-9)
    # зебра в текстуре дорожной плитки (L1: tex 106/111 — полосы и STOP): точки треугольника, чьи UV попадают в строки с полосами
    zrows = {}
    def zr(ti):
        if ti not in zrows: zrows[ti] = stripe_rows(G.level0(bb, trecs[ti])) if 0 <= ti < len(trecs) else None
        return zrows[ti]
    W_ = np.array([(i / 5, j / 5) for i in range(6) for j in range(6 - i)])   # сетка барицентрик
    ZP = []
    for k in np.where(ny > .9)[0]:
        rws = zr(int(TX[k]))
        if rws is None: continue
        bc = np.c_[W_, 1 - W_.sum(1)]; uv = bc @ UV[k]; wp = bc @ P[k]
        row = (np.mod(uv[:, 1], 1.0) * len(rws)).astype(int).clip(0, len(rws) - 1)
        ZP.append(wp)   # вся плитка с зеброй (полоса зебры внутри плитки лежит по UV по-разному; стоп — за задним краем плитки)
    ZP = np.concatenate(ZP) if ZP else np.zeros((0, 3))
    m = ((fl & F_LAYER) != 0) & (ny > .9)
    DP = P[m]; DPI = pi[m]; C = DP.mean(1)
    L = lanes(trf); rows = []; recs = []
    for road, lane, end, d, lw, line in L:
        dxz = np.array([d[0], d[2]]); dl = np.linalg.norm(dxz)
        if dl < 1e-6: continue
        f = dxz / dl; s = np.array([-f[1], f[0]])
        rel = C[:, [0, 2]] - end[[0, 2]]
        a = rel @ f; b = rel @ s
        near = (a > -BACK) & (a < AHEAD) & (np.abs(b) < max(lw, 3.0) / 2 + 1.0) & (np.abs(C[:, 1] - end[1]) < 2.0)
        best = 0.0
        for q in (np.unique(DPI[near]) if near.any() else []):
            mm = near & (DPI == q)
            V = DP[mm].reshape(-1, 3)[:, [0, 2]] - end[[0, 2]]
            va, vb = V @ f, V @ s
            if va.max() - va.min() <= ALONG_MAX and vb.max() - vb.min() >= ACROSS_MIN:
                best = max(best, -va.min() + MARGIN)
        if len(ZP):   # зебра в текстуре плитки
            relz = ZP[:, [0, 2]] - end[[0, 2]]; za = relz @ f; zb = relz @ s
            mz = (za > -ZBACK) & (za < AHEAD) & (np.abs(zb) < max(lw, 3.0) / 2 + .5) & (np.abs(ZP[:, 1] - end[1]) < 2.0)
            if mz.sum() >= 4: best = max(best, -za[mz].min() + MARGIN)
        if best > 0.3:
            off = min(best, CAP); recs.append((road, lane, off))
            rows.append(f'{road}\t{lane}\t{end[0]:.1f}\t{end[2]:.1f}\t{off:.2f}')
    Path(pre + '_stop875.bin').write_bytes(b'STP1' + struct.pack('<I', len(recs)) + b''.join(struct.pack('<HHf', r, k, o) for r, k, o in recs))
    Path(pre + '_zebra.tsv').write_text('# дорога\tполоса\tx\tz\tотступ_м (tools/scout/zebra.py)\n' + '\n'.join(rows) + '\n')
    try:
        from PIL import Image, ImageDraw
        allp = np.concatenate([l[5] for l in L]); mn = allp.min(0) - 10; mx = allp.max(0) + 10; sc = 1.2
        img = Image.new('RGB', (int((mx[0] - mn[0]) * sc), int((mx[1] - mn[1]) * sc)), (24, 24, 24)); dr = ImageDraw.Draw(img)
        tr = lambda p: ((p[0] - mn[0]) * sc, (mx[1] - p[1]) * sc)
        for l in L: dr.line([tr(p) for p in l[5]], fill=(90, 90, 90), width=1)
        S = {(r, k) for r, k, _ in recs}
        for l in L:
            if (l[0], l[1]) in S: x, y = tr(l[2][[0, 2]]); dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(240, 60, 60))
        img.save(pre + '_zebra.png')
    except Exception as e: print('карта не построена:', e)
    offs = np.array([o for _, _, o in recs]) if recs else np.zeros(1)
    print(f'{lv}: концов полос {len(L)}, с зеброй/стоп-линией {len(recs)} ({100 * len(recs) / max(len(L), 1):.0f}%), отступ медиана {np.median(offs):.1f} м, макс {offs.max():.1f} -> {pre}_stop875.bin')


if __name__ == '__main__':
    main()
