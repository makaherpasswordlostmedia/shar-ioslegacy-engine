#!/usr/bin/env python3
"""№409 — замер ступеней и сетки на свечении логотипа титульного экрана (Splash.pag, gamelogo.png диска).

  python tools/title_band.py КАДР.png [КАДР2.png ...]   [--json OUT]
  python tools/title_band.py --model                     # модели конвейера без эмулятора: вход, CLUT8, 5650 с/без дизеринга GE

Эталон — вход страницы логотипа (картинка диска в масштабе порта, tools/load_export.py), до палитры. Область — свечение
(тёмно-зелёный ореол вокруг знака: G > R, 3 <= G < 70, B < 40, непрозрачно; края знака исключены). По строкам:
  разных цветов в строке, длина ровной полосы (px между сменами цвета) — ступени;
  сетка 4x4 — доля энергии остатка (кадр минус размытие 3x3), объяснённая узором с периодом 4 по x и y (дизеринг GE рисует
  именно такой: железо и программный рендер эмулятора); у рассеяния без узора — около 0.
Выход: строка на кадр, код 0. Пороги — у гейта tests/title/title.sh."""
import argparse, json, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def logo_input():
    """вход страницы логотипа: картинка в масштабе порта (RGBA), как её видит quantize_page"""
    import ui_export as U, load_export as L
    got = []
    o1, o2 = U.quantize_page, U.quantize_page_565
    U.quantize_page = lambda img, n=255: (got.append(np.asarray(img).copy()), o1(img, n))[1]
    U.quantize_page_565 = lambda img, n=255: (got.append(np.asarray(img).copy()), o2(img, n))[1]
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as d:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                L.export('boot', Path(d) / 'b.shr', mocks=False)
    finally:
        U.quantize_page, U.quantize_page_565 = o1, o2
    return _pick(got)


def _pick(got):
    for g in got:
        a = g.astype(int)
        glow = (a[..., 1] > a[..., 0]) & (a[..., 1] >= 3) & (a[..., 1] < 70) & (a[..., 2] < 40) & (a[..., 3] == 255)
        if glow.sum() > 5000: return g
    raise SystemExit('нет страницы логотипа')


def glow_mask(src):
    a = src.astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g > r) & (g >= 3) & (g < 70) & (b < 40) & (a[..., 3] == 255)
    gy, gx = np.gradient(a[..., :3].sum(2).astype(float))   # края знака (резкий перепад во входе) — не свечение
    edge = np.hypot(gx, gy) > 12
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2): m &= ~np.roll(np.roll(edge, dy, 0), dx, 1)
    return m


def box3(x):
    p = np.pad(x, 1, mode='edge'); return sum(p[1 + dy:1 + dy + x.shape[0], 1 + dx:1 + dx + x.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.


def measure(img, m):
    """img (H,W,3) int в осях входа, m — маска свечения -> dict"""
    flats, distinct = [], []
    for y in range(img.shape[0]):
        xs = np.nonzero(m[y])[0]
        if len(xs) < 24: continue
        for seg in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1):
            if len(seg) < 24: continue
            row = img[y, seg]; ch = np.nonzero(np.abs(np.diff(row, axis=0)).max(1) > 0)[0]
            flats.append(len(seg) / (len(ch) + 1)); distinct.append(len(np.unique(row, axis=0)))
    g = img[..., 1].astype(float); r = g - box3(g)
    ys, xs = np.nonzero(m)
    res = r[ys, xs]; cls = (ys % 4) * 4 + (xs % 4)
    pat = np.array([res[cls == k].mean() if (cls == k).any() else 0. for k in range(16)])
    grid = float((pat[cls] ** 2).sum() / max((res ** 2).sum(), 1e-9))
    return dict(rows=len(flats), flat=float(np.median(flats)), distinct=float(np.median(distinct)), grid=grid,
                noise=float(np.sqrt((res ** 2).mean())))


def to5650(rgb, dither):
    o = rgb[..., :3].astype(int).copy()
    if dither:   # матрица GE порта (viewer/main.c sceGuSetDither)
        D = np.array([[-4, 0, -3, 1], [2, -2, 3, -1], [-3, 1, -4, 0], [3, -1, 2, -2]]); H, W = o.shape[:2]
        o = np.clip(o + np.tile(D, (H // 4 + 1, W // 4 + 1))[:H, :W, None], 0, 255)
    o[..., 0] = o[..., 0] >> 3 << 3; o[..., 1] = o[..., 1] >> 2 << 2; o[..., 2] = o[..., 2] >> 3 << 3
    return o


def align(frame, src):
    """логотип в кадре 480x272: сдвиг с наименьшим отличием от входа (непрозрачные пиксели)"""
    a = src[..., 3] == 255; h, w = src.shape[:2]; ys, xs = np.nonzero(src[..., 3] > 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; S = src[y0:y1, x0:x1, :3].astype(int); A = a[y0:y1, x0:x1]
    best = None
    for oy in range(-8, 24):
        for ox in range(0, 140):
            if oy < 0 or oy + (y1 - y0) > frame.shape[0] or ox + (x1 - x0) > frame.shape[1]: continue
            d = np.abs(frame[oy:oy + y1 - y0, ox:ox + x1 - x0] - S)[A].mean()
            if best is None or d < best[0]: best = (d, ox, oy)
    d, ox, oy = best
    out = np.zeros((h, w, 3), int); out[y0:y1, x0:x1] = frame[oy:oy + y1 - y0, ox:ox + x1 - x0]
    return out, (ox - x0, oy - y0, d)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('frames', nargs='*'); ap.add_argument('--model', action='store_true')
    ap.add_argument('--json'); a = ap.parse_args()
    src = logo_input(); m = glow_mask(src); out = {}
    def show(name, r): out[name] = r; print(f"{name:34s} строк {r['rows']:3d}  цветов в строке {r['distinct']:5.1f}  ровная полоса {r['flat']:4.1f} px  "
                                         f"сетка 4x4 {r['grid']:.3f}  шум {r['noise']:.2f}")
    show('вход (эталон, до палитры)', measure(src[..., :3].astype(int), m))
    if a.model:
        import ui_export as U
        idx, full = U.quantize_page(Image.fromarray(src)); q = full[idx]
        idx5, full5 = U.quantize_page_565(Image.fromarray(src)); q5 = full5[idx5]
        show('CLUT8 k-means (прежнее)', measure(q[..., :3].astype(int), m))
        show('прежнее -> 5650 без дизеринга', measure(to5650(q, False), m))
        show('прежнее -> 5650 дизеринг GE', measure(to5650(q, True), m))
        show('новое (5650 точно, рассеяние)', measure(to5650(q5, False), m))
    for f in a.frames:
        fr = np.asarray(Image.open(f).convert('RGB')).astype(int)
        al, (dx, dy, d) = align(fr, src)
        vis = m & (np.abs(al - src[..., :3].astype(int)).max(2) <= 24)   # не под рамкой-телевизором / надписью
        vis = vis & np.roll(vis, 1, 1) & np.roll(vis, -1, 1)
        r = measure(al, vis); r['offset'] = [int(dx), int(dy)]; r['match'] = float(d); show(f'кадр {Path(f).name} (сдвиг {dx},{dy})', r)
    if a.json: Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
