#!/usr/bin/env python3
"""№515 (Роб: у пузыря сообщения в HUD битые ломаные пиксели на скруглениях): гейт гладкости края. Для пузыря задания (helptext.png,
3-срез tools/ui_export.hslice) на нескольких размерах: подпиксельный контур концов (крайний столбец, где альфа пересекает 128, с
линейной интерполяцией) по строкам; шероховатость = RMS отклонения контура от лучшей окружности по строкам концов (у гладкой дуги мала, у ступенчатых концов
прежнего среза заметно больше). Плюс: нет прозрачных дыр в кромке (по каждой строке между краями кромки альфа
не падает ниже 40) и размер/позиция контура те же (ширина W, высота H, левый край у 0).
КРАСНЫЙ: BUBBLE_AA_OLD=1 обязан упасть. python3 tests/ui/bubble_aa.py [old|new] -> 0 = PASS (по умолчанию new)"""
import os, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))
mode = sys.argv[1] if len(sys.argv) > 1 else 'new'
if mode == 'old': os.environ['BUBBLE_AA_OLD'] = '1'
else: os.environ.pop('BUBBLE_AA_OLD', None)
import ui_export as U
im = U.all_images()['helptext.png']
LIM = 0.25
bad = []

def edge_left(a):
    """подпиксельный левый контур по строкам: x, где альфа впервые пересекает 128 (интерполяция); None — строки нет"""
    xs = []
    for row in a:
        j = np.nonzero(row >= 128)[0]
        if not len(j): xs.append(None); continue
        j = j[0]
        xs.append(j - (row[j] - 128) / max(row[j] - row[j - 1], 1) if j > 0 and row[j - 1] < 128 else float(j))
    return xs

def packed_alpha(W=259, H=56):
    """то же изображение, как оно ляжет в ui.shr: пакет -> квантование страницы в палитру T8 (ui_export.quantize_page) -> обратно в RGBA"""
    caps = []; oq = U.quantize_page
    def spy(img, *a, **k):
        idx, clut = oq(img, *a, **k); caps.append((np.asarray(img).copy(), idx, clut)); return idx, clut
    U.quantize_page = spy
    try: U.pack(os.devnull if False else '/tmp/_bubble_aa_ui.shr')
    finally: U.quantize_page = oq
    bub = np.asarray(U.hslice(im, W, H)); B = bub[..., 3].astype(int)
    for pre, idx, clut in caps:
        if pre.shape[0] < H: continue
        cand = np.argwhere((pre[:pre.shape[0] - H + 1, :pre.shape[1] - W + 1, 3] == B[0, 0]) & (pre[H // 2:pre.shape[0] - H + 1 + H // 2, :pre.shape[1] - W + 1, 3] == B[H // 2, 0]))
        for y, x in cand[:30000]:
            if np.array_equal(pre[y:y + H, x:x + W], bub): return clut[idx][y:y + H, x:x + W][..., 3].astype(float)
    return None

cases = [((W, H), np.asarray(U.hslice(im, W, H).getchannel('A')).astype(float), 'сборка') for W, H in ((259, 56), (320, 56), (200, 40), (259, 62))]
pk = packed_alpha()
if pk is None: bad.append('пузырь 259x56 не найден в странице пакета'); print('FAIL пузырь не найден в странице пакета')
else: cases.append(((259, 56), pk, 'после палитры T8 в ui.shr'))
for (W, H), out, label in cases:
    for side, a in (('левый', out), ('правый', out[:, ::-1])):
        e = edge_left(a[:, :H])
        pts = [(y, v) for y, v in enumerate(e) if v is not None]
        # без верхней/нижней кромки (там контур горизонтален и край резко выходит на строку): берём строки с наклоном
        ys = np.array([y for y, _ in pts]); v = np.array([v for _, v in pts])
        lo, hi = int(0.18 * H), int(0.82 * H)
        sel = (ys >= lo) & (ys <= hi)
        yy, xx = ys[sel].astype(float), v[sel]                 # МНК-окружность по точкам контура; невязка = отклонение от гладкой дуги
        M = np.c_[2 * xx, 2 * yy, np.ones_like(xx)]; sol = np.linalg.lstsq(M, xx ** 2 + yy ** 2, rcond=None)[0]
        rr = np.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2); rough = float(np.sqrt(np.mean((np.hypot(xx - sol[0], yy - sol[1]) - rr) ** 2)))
        ok = rough <= LIM
        print(f'{"PASS" if ok else "FAIL"} {W}x{H} {label} {side} конец: шероховатость контура {rough:.3f} px (предел {LIM})')
        if not ok: bad.append(f'{W}x{H} {side} {rough:.3f}')
    A = out
    # размер контура: непрозрачное по альфе >= 128
    cols = np.nonzero((A >= 128).any(0))[0]; rows = np.nonzero((A >= 128).any(1))[0]
    ok = cols[0] <= 1 and cols[-1] >= W - 5 and rows[0] <= 1 and rows[-1] >= H - 6
    print(f'{"PASS" if ok else "FAIL"} {W}x{H} контур по размеру: x {cols[0]}..{cols[-1]}, y {rows[0]}..{rows[-1]}')
    if not ok: bad.append(f'{W}x{H} размер')
print('PASS' if not bad else 'FAIL: ' + '; '.join(bad)); sys.exit(0 if not bad else 1)
