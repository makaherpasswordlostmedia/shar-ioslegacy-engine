#!/usr/bin/env python3
"""Фон игры в меню PSP (XMB), PIC1.PNG 480×272, из обложки Роба (build/assets/pic1-source-rob.png = его
Simpsons-Hit-and-Run-Cover.png 1280×720; официальный арт — только в build/, в git не попадает).

Правка Роба 30 (видео IMG_7656.MOV 0:22–0:34): «картинка ок, но дал бы её капельку правее» — прежний режим: окно
2,03 px обложки на px экрана, верх 84, левый край 1 + --shift·zoom (теперь только отрицательный контроль: --shift 28).

Правка Роба 132 (01.10): «фоновую картинку из моего исходника: Гомер не так близко, общий масштаб меньше, чтобы влезала
Мардж (сейчас её перекрывают рамки значков), всё правее и немного вверх». На видео Роба (IMG_7656.MOV 0:20) слева
столбец значков XMB, экранный x ~20–170. Мардж на обложке — коробка MARGE (px обложки). Чтобы она стояла правее
значков при мельче масштабе, левый край обложки уходит ВПРАВО от края экрана — слева пустая полоса (её заливка --fill).
Решено терминалом за Роба (он велел не спрашивать): масштаб 2,45 px обложки на px экрана (средний из предложенных
2,3 / 2,45 / 2,65: Гомер на 17% мельче), левый край Мардж на экране --marge-x 170 (сразу за столбцом значков), окно
по высоте прижато к низу обложки (y0 = 720 − 272·2,45 ≈ 54 — выше прежних 84: картинка на экране поднялась), полоса
слева тёмная (--fill dark, мягкий переход FEATHER px). Вкусовые ручки — ключи: --zoom, --marge-x, --y0, --fill dark|blur.
Пишет build/assets/pic1.png (RGB 480×272) и build/assets/pic1.json (параметры; tools/pbp_gate.py перерисовывает фон по
ним функцией render() и сверяет с PNG, а коробку Мардж пересчитывает на экран).
  tools/pic1.py [--src ...] [--out build/assets/pic1.png] [--zoom 2.45] [--marge-x 170] [--y0 Y] [--fill dark|blur]
  tools/pic1.py --shift 28 --zoom 2.03 --x0 1 --y0 84      прежний фон правки 30 (отрицательный контроль)"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
W, H = 480, 272
MARGE = (295, 448, 375, 620)   # Мардж с Мэгги на обложке Роба 1280×720, px (x0, y0, x1, y1): по листу обложки с сеткой
ICONS_X1 = 170                 # правый край столбца значков XMB на экране (видео Роба IMG_7656.MOV 0:20)
HAND_X = 997                   # кончик пальцев Гомера на обложке, px (жёлтое правее всех, y 391) — правка 204: руку не резать
OLD_X0 = 1 + 28 * 2.03         # окно 29.09 (правка 30), от него меряется сдвиг
# Правка Роба 204 (03.10 12:0x): «сдвинул раза в 3 больше, чем надо, обрезал руку Гомеру, слева больше места, чем нужно —
# усреднить, немножко, чтобы Мардж с Мэгги появлялись». Масштаб тот же 2,03 (правка 195), верх 84 (как 29.09); левый край
# Мардж на экране 132: сдвиг от 29.09 — 15 px (утром было 65), окно кончается правее руки (997 + 4), полосы слева нет
ZOOM = 2.03
MARGE_X = 132
# Правка Роба 204, 12:1x: «вот я тебе сам их обрезал, подставь вот так» — build/assets/pic1-crop-rob-0310.png (его Desktop/Asset
# 1@2x.png, 2530×1445, слева 44 px прозрачно). Окно найдено сопоставлением с обложкой (k 2,16 px артборда на px обложки, ошибка 6/255):
# обложка x −20,4..1150,9, y 6,8..675,7; на 480×272 — масштаб по ширине 2,4402, по высоте середина (обрезка 2,6 px сверху и снизу),
# полоса слева 8,4 px — как прозрачный край его артборда (на PSP прозрачности нет — тёмная, без растушёвки)
ROB_CROP = 'build/assets/pic1-crop-rob-0310.png'
ROB_WIN = (-20.37, 9.43, 2.4402)   # x0, y0, zoom
# Правка Роба 261 (04.10: «поставить картинку так, чтобы не было обрезания для PSP меню»): обложка целиком — по высоте 720 px на 272
# строки экрана (масштаб 2,647), по ширине 1270,6 из 1280 (по 4,7 px с краёв, 0,7 %), без тёмной полосы слева. --rob-crop — окно 204
FULL_WIN = (4.7, 0.0, 2.647058)
FEATHER = 18                   # px экрана: мягкий переход от обложки к тёмной полосе слева
FILL_DARK = (6, 6, 8)          # цвет полосы слева (--fill dark), почти чёрный, как фон ICON0


def render(src, zoom, x0, y0, dim, fill='dark', feather=FEATHER):
    """Окно обложки (x0, y0) .. + 480·zoom × 272·zoom -> PIL RGB 480×272; окно может выходить за левый край обложки
    (правка 132): там полоса --fill (dark — тёмная, blur — размытое продолжение края), шов смягчён на feather px."""
    src = Image.open(src).convert('RGB')
    box = (x0, y0, x0 + W * zoom, y0 + H * zoom)
    if box[2] > src.width + 0.01 or box[3] > src.height + 0.01 or box[1] < -0.01:   # 0,01: округление pic1.json
        raise SystemExit(f'окно {tuple(round(v, 1) for v in box)} за краем обложки {src.size}')
    pad = max(0, int(np.ceil(-x0)) + 8)
    if pad:   # обложка на холст с полосой слева, окно сдвигается на неё же
        canvas = Image.new('RGB', (src.width + pad, src.height), FILL_DARK)
        if fill == 'blur':
            edge = src.crop((0, 0, min(pad, src.width), src.height)).transpose(Image.FLIP_LEFT_RIGHT)
            canvas.paste(ImageEnhance.Brightness(edge.filter(ImageFilter.GaussianBlur(24))).enhance(0.45), (0, 0))
        canvas.paste(src, (pad, 0)); src = canvas
        box = (box[0] + pad, box[1], box[2] + pad, box[3])
    pic = src.resize((W, H), Image.LANCZOS, box=box)
    if dim < 1.0:   # правка 68: темнее, серые элементы XMB в тон
        pic = ImageEnhance.Brightness(pic).enhance(dim)
    if x0 < 0 and fill == 'dark' and feather > 0:   # шов: обложка плавно уходит в тёмную полосу
        sx = -x0 / zoom; a = np.asarray(pic, np.float32)
        t = np.clip((np.arange(W) - sx) / feather, 0.0, 1.0)[None, :, None]
        a = a * t + np.array(FILL_DARK, np.float32) * (1 - t)
        pic = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), 'RGB')
    return pic


def marge_on_screen(meta):
    """Коробка Мардж (MARGE, px обложки) на экране PSP по параметрам pic1.json."""
    z, x0, y0 = meta['zoom'], meta['box'][0], meta['box'][1]
    return tuple((v - o) / z for v, o in zip(MARGE, (x0, y0, x0, y0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(ROOT / 'build/assets/pic1-source-rob.png'))
    ap.add_argument('--out', default=str(ROOT / 'build/assets/pic1.png'))
    ap.add_argument('--dim', type=float, default=0.62, help='правка Роба 68: «фон слишком яркий — затемнить, чтобы серый был в тон» — множитель яркости')
    ap.add_argument('--zoom', type=float, default=ZOOM, help='px обложки на px экрана (правки 195/204: 2,03, как 29.09)')
    ap.add_argument('--marge-x', type=float, default=MARGE_X, help='левый край Мардж на экране, px (правка 204: 132 — сдвиг 15 px от 29.09)')
    ap.add_argument('--y0', type=float, default=84.0, help='верх окна на обложке, px (правка 204: 84, как 29.09)')
    ap.add_argument('--fill', default='dark', choices=['dark', 'blur'], help='полоса слева, где обложки нет')
    ap.add_argument('--shift', type=float, help='прежний режим правки 30: сдвиг окна вправо, px экрана (только отрицательный контроль)')
    ap.add_argument('--x0', type=float, default=1.0, help='прежний режим: левый край прежнего окна на обложке, px')
    ap.add_argument('--window', type=float, nargs=3, metavar=('X0', 'Y0', 'ZOOM'), help='окно обложки прямо (по умолчанию — обрезка Роба 204)')
    ap.add_argument('--auto', action='store_true', help='прежний подбор по --marge-x (до обрезки Роба)')
    ap.add_argument('--rob-crop', action='store_true', help='прежнее окно обрезки Роба (правка 204), до правки 261')
    a = ap.parse_args()
    src_im = Image.open(a.src)
    feather = FEATHER
    if a.window or (not a.auto and a.shift is None):   # правка 204: окно обрезки Роба
        x0, y0, a.zoom = a.window if a.window else (ROB_WIN if a.rob_crop else FULL_WIN); feather = 0; a.marge_x = None
        pic = render(a.src, a.zoom, x0, y0, a.dim, a.fill, feather)
        pic.save(a.out, optimize=True)
        box = (x0, y0, x0 + W * a.zoom, y0 + H * a.zoom)
        meta = dict(dim=a.dim, src=Path(a.src).name, src_sha256=hashlib.sha256(Path(a.src).read_bytes()).hexdigest(), zoom=a.zoom,
                    fill=a.fill, feather=feather, box=[round(v, 3) for v in box], shift=None, marge_x=None, rob_crop=ROB_CROP if (a.rob_crop and not a.window) else None)
        mg = marge_on_screen(meta); meta['marge_screen'] = [round(v, 1) for v in mg]
        Path(a.out).with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        print(f'{a.out}: окно обрезки Роба — масштаб {a.zoom:g}, обложка {box[0]:.1f}..{box[2]:.1f} x {box[1]:.1f}..{box[3]:.1f}, '
              f'полоса слева {max(0.0, -x0 / a.zoom):.1f} px; Мардж на экране x {mg[0]:.0f}..{mg[2]:.0f}')
        return
    if a.shift is not None:
        x0 = a.x0 + a.shift * a.zoom; y0 = 84.0 if a.y0 is None else a.y0
    else:
        x0 = MARGE[0] - a.marge_x * a.zoom; y0 = src_im.height - H * a.zoom if a.y0 is None else a.y0
    pic = render(a.src, a.zoom, x0, y0, a.dim, a.fill)
    pic.save(a.out, optimize=True)
    box = (x0, y0, x0 + W * a.zoom, y0 + H * a.zoom)
    meta = dict(dim=a.dim, src=Path(a.src).name, src_sha256=hashlib.sha256(Path(a.src).read_bytes()).hexdigest(), zoom=a.zoom,
                fill=a.fill, feather=FEATHER, box=[round(v, 3) for v in box], shift=a.shift, marge_x=None if a.shift is not None else a.marge_x)
    mg = marge_on_screen(meta); meta['marge_screen'] = [round(v, 1) for v in mg]
    Path(a.out).with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f'{a.out}: {W}x{H} RGB, масштаб {a.zoom:g}, окно обложки {box[0]:.0f}..{box[2]:.0f} x {box[1]:.0f}..{box[3]:.0f} из {src_im.size}, '
          f'полоса слева {max(0.0, -x0 / a.zoom):.0f} px ({a.fill}); Мардж на экране x {mg[0]:.0f}..{mg[2]:.0f}, y {mg[1]:.0f}..{mg[3]:.0f}')


if __name__ == '__main__':
    main()
