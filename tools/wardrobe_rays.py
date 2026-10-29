#!/usr/bin/env python3
"""№703: фон гардероба с лучами, запечённый в ОДНУ непрозрачную картинку 480x272 (вместо градиента BGColour + 16 клиньев с альфой).

Раньше (№695, viewer/wardrobe_view.c drawRays): поверх градиента страницы рисуются 16 клиньев из точки у ног Гомера, цвет 0x00ffd8c8,
альфа WV_RAY_A у центра. Здесь те же числа сводятся офлайн: градиент по строкам (цвета из пакета страницы) + клинья с тем же смешиванием
dst*(1-a) + src*a, каждый клин — тот же треугольник с вершинами, усечёнными до short, как делает движок. Результат кладётся в пакет
гардероба отдельным слоем (тег WASPS), движок рисует его одним непрозрачным спрайтом без смешивания и без клиньев
(viewer/wardrobe_view.c; WARDROBE_RAYBAKE_OLD=1 при сборке или файл raysold рядом с EBOOT — прежний вариант: градиент + клинья).

Константы ДОЛЖНЫ совпадать с viewer/wardrobe_view.c (WV_RAYS, WV_RAY_A, WV_RAY_R, цвет, 0.45 роста): гейт tests/shop/wardrobe_rays.sh сверяет их по тексту.

  python tools/wardrobe_rays.py --png out.png [--view CX CY HPX]   # картинка для просмотра/гейта (RGB, без квантования)
"""
import argparse, math, os, sys
import numpy as np

W, H = 480, 272
RAYS, RAY_A, RAY_R = 16, 24, 340.0          # = WV_RAYS, WV_RAY_A, WV_RAY_R
RAY_RGB = (0xc8, 0xd8, 0xff)                # цвет 0x00ffd8c8 в ABGR: R=c8 G=d8 B=ff
# Калибровка по эмулятору (PPSSPP, безголовый): вклад клина на кадре в ~0,7 от номинала RAY_A * вес центральной вершины (измерено по кадрам старого
# рисования, tests/shop/wardrobe_rays.sh; на железе вклад может отличаться на 1–2 уровня, лучи «еле заметные»). WARDROBE_RAY_GAIN=0 — красный контроль гейта
RAY_GAIN = float(os.environ.get('WARDROBE_RAY_GAIN', '0.7'))
FOOT = 0.45                                 # центр клиньев: vCy + vHpx * FOOT
# №732 (Роб 17.10, видео IMG_7280 9:30: «лучи прикольные, но не внизу, а по центру экрана; их слишком много»): запечённый фон — центр клиньев
# в середине экрана, клиньев 12 вместо 16. WARDROBE_RAYS732_OLD=1 — как №695/№703 (16 из точки у ног; так же рисует движок по файлу raysold)
RAYS732 = 12
RAYS732_OLD = os.environ.get('WARDROBE_RAYS732_OLD') == '1'


def gradient(top, bottom):
    """вертикальный градиент как у GE: цвет строки y считается в центре пикселя (y + .5) / H"""
    t = ((np.arange(H, dtype=np.float64) + .5) / H)[:, None, None]
    c0 = np.array(top[:3], np.float64)[None, None, :]; c1 = np.array(bottom[:3], np.float64)[None, None, :]
    return np.broadcast_to(c0 + (c1 - c0) * t, (H, W, 3)).copy()


def wedge_mask(cx, cy, rays=RAYS):
    """битовая маска 480x272: объединение 16 клиньев (они не перекрываются); вершины усечены до short, центр пикселя (x+.5, y+.5)"""
    ys, xs = np.mgrid[0:H, 0:W]; px = xs + .5; py = ys + .5
    m = np.zeros((H, W), bool); w0 = np.zeros((H, W))   # w0 — барицентрический вес центральной вершины: альфа A у центра -> 0 на дальних (Гуро)
    tr = lambda v: float(np.fix(v))        # (short) от float — к нулю
    for i in range(rays):
        a0 = i * 6.2831853 / rays; a1 = a0 + 3.1415927 / rays
        p = [(tr(cx), tr(cy)), (tr(cx + math.cos(a0) * RAY_R), tr(cy + math.sin(a0) * RAY_R)), (tr(cx + math.cos(a1) * RAY_R), tr(cy + math.sin(a1) * RAY_R))]
        (x0, y0), (x1, y1), (x2, y2) = p
        d = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if d == 0: continue
        e0 = ((x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)) / d     # барицентрические веса
        e1 = ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) / d
        e2 = 1.0 - e0 - e1
        eps = 1e-9
        ins = (e0 >= -eps) & (e1 >= -eps) & (e2 >= -eps)
        m |= ins; w0[ins] = e1[ins]
    return m, w0


def bake(top, bottom, view):
    """-> RGB uint8 (H, W, 3): градиент + лучи; view = (vCx, vCy, vHpx) как строка «view» skins.txt"""
    vcx, vcy, vh = view
    img = gradient(top, bottom)
    m, w0 = wedge_mask(vcx, vcy + vh * FOOT) if RAYS732_OLD else wedge_mask(W / 2, H / 2, RAYS732)   # №732: центр экрана, 12 клиньев
    a = RAY_A * RAY_GAIN / 255.0 * w0
    for k in range(3):
        img[..., k] = img[..., k] * (1.0 - a) + RAY_RGB[k] * a
    return np.clip(img + .5, 0, 255).astype(np.uint8), m


def bake_at(top, bottom, cx, cy, rays=RAYS732):
    """Роб 17.10 (будка): те же лучи, центр в точке (cx, cy) — за машиной; -> RGB uint8 (H, W, 3)"""
    img = gradient(top, bottom)
    m, w0 = wedge_mask(cx, cy, rays)
    a = RAY_A * RAY_GAIN / 255.0 * w0
    for k in range(3):
        img[..., k] = img[..., k] * (1.0 - a) + RAY_RGB[k] * a
    return np.clip(img + .5, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--png'); ap.add_argument('--view', nargs=3, type=float, default=[240.0, 134.0, 183.0])
    ap.add_argument('--top', nargs=3, type=int, default=[90, 99, 180]); ap.add_argument('--bottom', nargs=3, type=int, default=[37, 43, 67])
    a = ap.parse_args()
    img, m = bake(a.top, a.bottom, tuple(a.view))
    print('лучи: %d px из %d (%.1f %%), клиньев %d, альфа %d, радиус %g' % (m.sum(), W * H, 100.0 * m.sum() / (W * H), RAYS if RAYS732_OLD else RAYS732, RAY_A, RAY_R))
    if a.png:
        from PIL import Image; Image.fromarray(img, 'RGB').save(a.png)


if __name__ == '__main__':
    main()
