#!/usr/bin/env python3
"""Правка Роба 340: разбор прогона tests/guard340/mac_foot.txt (безголовый эмулятор: программная отрисовка PPSSPP выбрасывает
треугольник за защитной полосой, как железо) или части тура на PSP (tests/guard340/psp_test_foot.txt).
  python3 tests/guard340/emu340.py ПАПКА [--level build/level.shr] [--sheet OUT.png] [--poses SMOKE.txt]
У каждой позы два снимка: P?_old (flag ggold 1 — прежнее) и P?_new (срез по полосе). По строке CAMF перед снимком прежнего —
модель GE (tests/guard340/ge340.py): какие треугольники GE выбросил бы, их видимая площадь (маска на экране).
Проверка позы с потерями (≥ 5000 px по модели): новое отличается от прежнего внутри маски выброшенного (≥ 20 % её площади —
GE теперь рисует то, что раньше выбрасывал; часть маски закрыта Гомером, радаром или совпадает по цвету) и почти не отличается
вне её (≤ 3 % кадра, без прямоугольника Гомера и радара — их анимация между снимками не в счёт);
поза без потерь (ближняя 1,5 м): кадры равны с той же поправкой на анимацию. Без строк CAMF (тур PSP без camlog) — только
отличия кадров и снимок-лист."""
import argparse, glob, math, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ge340 as G
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def shot_poses(smoke):
    out = {}; prev = None
    for l in open(smoke, errors='replace'):
        if l.startswith('CAMF '): prev = l
        if l.startswith('SHOT ') and prev:
            d = dict(re.findall(r'(\w+)=([^\s]+)', prev)); nm = l.split()[1]
            out[nm] = (np.array([float(x) for x in d['eye'].split(',')]), np.array([float(x) for x in d['look'].split(',')]),
                       float(d['fov']), float(d.get('near', 1.5)), np.array([float(x) for x in d['homer'].split(',')]))
    return out


def drop_mask(L, eye, at, fov, near, radius=60.):
    """маска экрана треугольников, которые GE выбросил бы (прежнее), и их видимая площадь"""
    r, u, f = G.basis(eye, at); tvy = math.tan(math.radians(fov) / 2); tvx = tvy * G.ASPECT
    idx = np.nonzero(np.linalg.norm(L['C'] - eye, axis=1) < radius)[0]; T = L['P'][idx] - eye; V = np.stack([T @ r, T @ u, T @ f], -1)
    x, y, z = V[..., 0], V[..., 1], V[..., 2]
    out = (z < near).all(1) | (x > tvx * z).all(1) | (-x > tvx * z).all(1) | (y > tvy * z).all(1) | (-y > tvy * z).all(1)
    m = Image.new('L', (480, 272), 0); dr = ImageDraw.Draw(m); area = 0.
    for k in np.nonzero(~out)[0]:
        a, drop = G.ge(V[k], near, tvx, tvy)
        if not drop or a < .5: continue
        area += a; poly = G.clip_near(list(V[k]), near)
        sx = 240 + poly[:, 0] / poly[:, 2] / tvx * 240; sy = 136 - poly[:, 1] / poly[:, 2] / tvy * 136
        dr.polygon([(float(np.clip(px, -9e3, 9e3)), float(np.clip(py, -9e3, 9e3))) for px, py in zip(sx, sy)], fill=255)
    return np.asarray(m) > 0, area


def homer_box(eye, at, fov, homer):
    """прямоугольник экрана вокруг Гомера (цилиндр 0,8 м × 2,1 м) — его анимация между снимками не в счёт"""
    r, u, f = G.basis(eye, at); tvy = math.tan(math.radians(fov) / 2); tvx = tvy * G.ASPECT
    pts = np.array([homer + [dx, dy, dz] for dx in (-.8, .8) for dy in (-.1, 2.2) for dz in (-.8, .8)]) - eye
    x, y, z = pts @ r, pts @ u, np.maximum(pts @ f, .05)
    sx = 240 + x / z / tvx * 240; sy = 136 - y / z / tvy * 136
    m = np.zeros((272, 480), bool); x0, x1 = int(max(0, sx.min() - 6)), int(min(480, sx.max() + 6)); y0, y1 = int(max(0, sy.min() - 6)), int(min(272, sy.max() + 6))
    if x0 < x1 and y0 < y1: m[y0:y1, x0:x1] = True
    m[195:268, 378:465] = True   # радар интерфейса (монеты, стрелка — анимация)
    return m


def dilate(m, r=2):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1): o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--level', default=str(ROOT / 'build/level.shr')); ap.add_argument('--sheet')
    ap.add_argument('--poses', help='smoke.txt другого прогона того же сценария — позы камеры оттуда (движок до правки не пишет near в CAMF)')
    a = ap.parse_args(); d = Path(a.dir)
    sh = d / 'shots' if (d / 'shots').is_dir() and glob.glob(str(d / 'shots' / 'P*_old.*')) else d
    names = sorted({re.sub(r'_(old|new)$', '', Path(f).stem) for f in glob.glob(str(sh / 'P*_old.*'))})
    if not names: print(f'нет снимков P*_old в {sh}'); return 1
    smoke = Path(a.poses) if a.poses else d / 'smoke.txt'; poses = shot_poses(smoke) if smoke.exists() else {}
    L = G.level(a.level) if poses else None
    ok = True; rows = []; nlost = 0
    print('поза  ближняя  потеряно GE (модель, px)  отличий нового от прежнего: в маске выброшенного | вне её   итог')
    for nm in names:
        def img(tag):
            f = next(iter(glob.glob(str(sh / f'{nm}_{tag}.png')) + glob.glob(str(sh / f'{nm}_{tag}.bmp'))), None)
            return np.asarray(Image.open(f).convert('RGB')).astype(int) if f else None
        o, n = img('old'), img('new')
        if o is None or n is None: print(f'{nm}: нет пары снимков'); ok = False; continue
        diff = np.abs(o - n).max(2) > 8
        pose = poses.get(f'{nm}_old')
        if pose is None or L is None:
            print(f'{nm}   ?        ?                      всего отличий {diff.sum()}'); rows.append((nm, o, n, diff)); continue
        eye, at, fov, near, homer = pose
        m, area = drop_mask(L, eye, at, fov, near); md = dilate(m, 3); hb = homer_box(eye, at, fov, homer)
        inside = (diff & md).sum(); outside = (diff & ~md & ~hb).sum(); mvis = m.sum()
        if area >= 5000:
            nlost += 1; good = inside >= .2 * mvis and outside <= .03 * diff.size
        else:
            good = outside <= .03 * diff.size
        ok &= good
        print(f'{nm}   {near:5.2f}   {area:10.0f}              {inside:6d} из {mvis:6d} | {outside:6d}   {"да" if good else "НЕТ"}')
        rows.append((nm, o, n, diff | (m & ~diff) * 0))
    if a.sheet and rows:
        W, H = 320, 181; sheet = Image.new('RGB', (W * 3, H * len(rows)))
        for j, (nm, o, n, df) in enumerate(rows):
            for i, im in enumerate((o, n, np.repeat(df[..., None], 3, 2) * 255)):
                sheet.paste(Image.fromarray(im.astype(np.uint8)).resize((W, H)), (i * W, j * H))
        sheet.save(a.sheet); print('лист (прежнее | новое | отличия):', a.sheet)
    if poses: print(f'ИТОГ: {"зелёный" if ok and nlost >= 2 else "КРАСНЫЙ"} — поз с потерями по модели {nlost}; новое рисует выброшенное и больше ничего не меняет'
                    if ok and nlost >= 2 else f'ИТОГ: КРАСНЫЙ — поз с потерями {nlost}, проверка {"прошла" if ok else "не прошла"}')
    return 0 if (ok and nlost >= 2) or not poses else 1


if __name__ == '__main__':
    sys.exit(main())
