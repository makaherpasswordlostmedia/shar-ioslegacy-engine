#!/usr/bin/env python3
"""Коды мест (правка Роба 58): код из служебного счётчика («L1 D7-5») <-> точка карты. Правило сетки — viewer/placecode.h
(то же самое здесь; сверка C и Python — tests/placecode/gate.sh).

  python tools/place.py D7-5                 # уровень 1: центр участка (координаты движка и игры), ближайшие места, строка goto
  python tools/place.py "L4 Д7 5"            # голосом/по-русски: буквы кириллицей, пробелы вместо дефиса
  python tools/place.py --at 209 285         # координаты движка -> код
  python tools/place.py --sheet 1            # лист карты уровня с сеткой -> build/maps/l1_codes.png (из данных диска, не в git)

Квадрат 100 м: буква столбца по x (A…M без I), число ряда по z движка (1…15); участок 33 м — цифра 1…9 как на кнопках
телефона (1 2 3 — ряд с меньшим z). Координаты движка = координаты level.shr и команды goto смоука (z игры зеркален).
Места — AddTeleportDest из скриптов уровня (scripts/missions/level0N/*.mfk) — названия оригинала."""
import argparse, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'hit-and-run-web/source/game'
X0, Z0, CELL, COLS, ROWS = -700.0, -700.0, 100.0, 12, 15
LETTERS = 'ABCDEFGHJKLM'
CYR = {'А': 'A', 'Б': 'B', 'В': 'B', 'С': 'C', 'Ц': 'C', 'Д': 'D', 'Е': 'E', 'Э': 'E', 'Ф': 'F', 'Г': 'G', 'Х': 'H', 'Н': 'H',
       'Й': 'J', 'Ж': 'J', 'К': 'K', 'Л': 'L', 'М': 'M'}


def code(x, z):
    """Код места; за сеткой — ближайшее место на краю (№688), '--' только для не-числа. То же правило, что viewer/placecode.h"""
    fx, fz = (x - X0) / CELL, (z - Z0) / CELL
    if fx != fx or fz != fz: return '--'
    if fx < 0: c, sx = 0, 0
    elif fx >= COLS: c, sx = COLS - 1, 2
    else: c = math.floor(fx); sx = min(2, math.floor((fx - c) * 3))
    if fz < 0: r, sz = 0, 0
    elif fz >= ROWS: r, sz = ROWS - 1, 2
    else: r = math.floor(fz); sz = min(2, math.floor((fz - r) * 3))
    return f'{LETTERS[c]}{r + 1}-{1 + sx + 3 * sz}'


def parse(s):
    """'L1 D7-5' / 'д7 5' / 'D7' -> (уровень или None, столбец, ряд, участок или None)"""
    t = s.strip().upper()
    t = ''.join(CYR.get(ch, ch) for ch in t)
    lv = None
    m = re.match(r'^[LЛ]\s*(\d)\s*[ ,.-]?\s*(?=[A-Z])', t)
    if m: lv = int(m.group(1)); t = t[m.end():]
    m = re.match(r'^([A-Z])\s*(\d{1,2})(?:\s*[- ,.]\s*([1-9]))?\s*$', t)
    if not m or m.group(1) not in LETTERS: raise SystemExit(f'не код: {s!r} (пример: D7-5, L1 D7-5, д7 5)')
    c, r = LETTERS.index(m.group(1)), int(m.group(2)) - 1
    if not 0 <= r < ROWS: raise SystemExit(f'ряд {r + 1} вне сетки 1…{ROWS}')
    return lv, c, r, int(m.group(3)) if m.group(3) else None


def center(c, r, sub):
    if sub is None: return X0 + (c + .5) * CELL, Z0 + (r + .5) * CELL, CELL / 2
    sx, sz = (sub - 1) % 3, (sub - 1) // 3
    return X0 + (c + (sx + .5) / 3) * CELL, Z0 + (r + (sz + .5) / 3) * CELL, CELL / 6


def places(level):
    """AddTeleportDest оригинала -> [(имя, x, z движка)]"""
    out = []
    for f in sorted((GAME / 'scripts/missions' / f'level{level:02d}').glob('*.mfk')):
        for m in re.finditer(r'AddTeleportDest\(\s*"([^"]+)"\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)', f.read_text(errors='replace')):
            nm, x, z = m.group(1), float(m.group(2)), -float(m.group(4))
            if all(nm != o[0] for o in out): out.append((nm, x, z))
    return out


def side(dx, dz):
    """направление по листу карты: x вправо, z движка вниз"""
    a = math.degrees(math.atan2(dz, dx)) % 360
    return ['справа', 'справа-снизу', 'снизу', 'слева-снизу', 'слева', 'слева-сверху', 'сверху', 'справа-сверху'][int((a + 22.5) // 45) % 8]


def report(s, level):
    lv, c, r, sub = parse(s)
    level = lv or level
    x, z, half = center(c, r, sub)
    cd = f'{LETTERS[c]}{r + 1}' + (f'-{sub}' if sub else '')
    print(f'L{level} {cd}: центр x {x:.0f}, z {z:.0f} (движок; игра z {-z:.0f}), участок ±{half:.0f} м')
    pl = sorted(places(level), key=lambda p: math.hypot(p[1] - x, p[2] - z))
    for nm, px, pz in pl[:3]:
        d = math.hypot(px - x, pz - z)
        print(f'  {nm}: {d:.0f} м' + (f', {side(px - x, pz - z)} по листу ({code(px, pz)})' if d > 15 else ' — здесь'))
    print(f'  смоук: goto {x:.0f} {z:.0f} 0')


def tex_means(b):
    """средний цвет каждой текстуры SHR7 (палитра по гистограмме нулевого уровня; шаг по уровням — как viewer/main.c)"""
    import numpy as np, struct
    ntex = struct.unpack_from('<I', b, 4)[0]
    W, H = struct.unpack_from('<II', b, 12 + 14 * 4)
    p = (104 + W * H * 8 + 15) & ~15; p = (p + W * H * 4 + 15) & ~15   # высоты, стены — с выравниванием 16 (main.c)
    out = []
    for _ in range(ntex):
        w, h, lv = struct.unpack_from('<HHH', b, p); pre = b[p + 7] == 1; t4 = b[p + 6] == 4   # T4 — правка 129
        pal = np.frombuffer(b, np.uint8, 1024, p + 16).reshape(256, 4).astype(np.float64); p += 16 + 1024
        lw, lh = w, h
        for l in range(lv):
            rb = max(16, (lw + 1) // 2) if t4 else (16 if pre and lw < 16 else lw)   # строка движка (main.c texRowBytes)
            n = rb * (((lh + 7) & ~7) if pre else lh)
            if l == 0:
                raw = np.frombuffer(b, np.uint8, n, p)
                if t4: raw = np.concatenate([raw & 15, raw >> 4])   # полубайты (порядок не важен для гистограммы)
                hist = np.bincount(raw, minlength=256).astype(np.float64)
                a = pal[:, 3] * hist; out.append((pal[:, :3] * a[:, None]).sum(0) / max(a.sum(), 1))
            p = (p + n + 15) & ~15; lw >>= 1; lh = lh >> 1 if lh > 1 else 1
    return out


def sheet(level):
    sys.path.insert(0, str(ROOT / 'tools'))
    from PIL import Image, ImageDraw, ImageFont
    import ui_export as U
    m = U.bake_radar_map(level)
    lo, hi = m['lo'], m['hi']                                   # игра: x, z
    M_ = 60.0   # запас за кольцом карты радара: край города (в сетке)
    xa, xb = max(0, math.floor((lo[0] - M_ - X0) / CELL)), min(COLS, math.ceil((hi[0] + M_ - X0) / CELL))
    za, zb = max(0, math.floor((-hi[1] - M_ - Z0) / CELL)), min(ROWS, math.ceil((-lo[1] + M_ - Z0) / CELL))
    PX, PAD = 1.0, 40                                           # пикселей на метр, поля под подписи
    W, H = int((xb - xa) * CELL * PX) + 2 * PAD, int((zb - za) * CELL * PX) + 2 * PAD
    img = Image.new('RGB', (W, H), (238, 236, 228)); dr = ImageDraw.Draw(img)
    ex = lambda x: PAD + (x - (X0 + xa * CELL)) * PX
    ez = lambda z: PAD + (z - (Z0 + za * CELL)) * PX
    # подложка: город уровня сверху (level.shr, ближняя версия), треугольник — средним цветом своей текстуры, снизу вверх
    import numpy as np
    import shr7read
    lp = ROOT / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
    if lp.exists():
        L = shr7read.load(lp); means = tex_means(lp.read_bytes())
        P = L['P']; keep = (L['FL'] & 4) == 0
        order = np.argsort(P[:, :, 1].max(1)); pale = lambda c: tuple(int(v * .55 + 238 * .45) for v in c)
        for i in order:
            if not keep[i] or L['TEX'][i] < 0: continue
            q = P[i]; dr.polygon([(ex(q[k, 0]), ez(q[k, 2])) for k in range(3)], fill=pale(means[L['TEX'][i]]))
    else: print(f'нет {lp.relative_to(ROOT)}: лист без подложки')
    try: font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 22)
    except OSError: font = ImageFont.load_default()
    try: small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
    except OSError: small = font
    for c in range(xa, xb + 1):
        X = ex(X0 + c * CELL); dr.line([X, PAD, X, H - PAD], fill=(200, 60, 40), width=2)
        for k in (1, 2):
            if c < xb: xx = ex(X0 + (c + k / 3) * CELL); dr.line([xx, PAD, xx, H - PAD], fill=(230, 180, 170), width=1)
        if c < xb and 0 <= c < COLS:
            t = LETTERS[c]; dr.text((ex(X0 + (c + .5) * CELL) - 7, 8), t, fill=(200, 60, 40), font=font)
            dr.text((ex(X0 + (c + .5) * CELL) - 7, H - PAD + 8), t, fill=(200, 60, 40), font=font)
    for r in range(za, zb + 1):
        Z = ez(Z0 + r * CELL); dr.line([PAD, Z, W - PAD, Z], fill=(200, 60, 40), width=2)
        for k in (1, 2):
            if r < zb: zz = ez(Z0 + (r + k / 3) * CELL); dr.line([PAD, zz, W - PAD, zz], fill=(230, 180, 170), width=1)
        if r < zb and 0 <= r < ROWS:
            t = str(r + 1); dr.text((6, ez(Z0 + (r + .5) * CELL) - 12), t, fill=(200, 60, 40), font=font)
            dr.text((W - PAD + 6, ez(Z0 + (r + .5) * CELL) - 12), t, fill=(200, 60, 40), font=font)
    boxes = []
    for nm, x, z in places(level):
        X, Z = ex(x), ez(z)
        dr.ellipse([X - 5, Z - 5, X + 5, Z + 5], fill=(40, 90, 220))
        t = f'{nm} ({code(x, z)})'; tw = dr.textlength(t, font=small); ty = Z - 9
        while any(X + 8 < b[2] and b[0] < X + 8 + tw and ty < b[3] and b[1] < ty + 16 for b in boxes): ty += 16   # подписи не наезжают
        if ty != Z - 9: dr.line([X, Z, X + 8, ty + 8], fill=(40, 90, 220))
        dr.rectangle([X + 6, ty, X + 10 + tw, ty + 16], fill=(255, 255, 255))
        dr.text((X + 8, ty), t, fill=(20, 40, 120), font=small); boxes.append((X + 8, ty, X + 8 + tw, ty + 16))
    dr.text((PAD + 6, PAD + 4), f'L{level}: квадрат 100 м (буква + ряд), участок 33 м = цифра 1-9 как на телефоне (1 2 3 сверху)',
            fill=(60, 60, 60), font=small)
    out = ROOT / 'build/maps' / f'l{level}_codes.png'; out.parent.mkdir(parents=True, exist_ok=True); img.save(out)
    print(f'лист: {out.relative_to(ROOT)} ({W}x{H}, 1 px = {1 / PX:.0f} м)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('code', nargs='?'); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--at', nargs=2, type=float); ap.add_argument('--sheet', type=int)
    a = ap.parse_args()
    if a.sheet: sheet(a.sheet)
    elif a.at: print(f'L{a.level} {code(*a.at)}')
    elif a.code: report(a.code, a.level)
    else: ap.print_help()
