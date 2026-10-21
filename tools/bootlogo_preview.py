#!/usr/bin/env python3
"""Превью анимации логотипа GONE Makers на заставке (пункт Л, просьба Роба 28.09) на Маке, тем же алгоритмом, что
viewer/bootscreen.h: диагональная волна (x + 2y), точка «набирает вес» символами / → | → \\ → ■, цвет от блика к покою.
Варианты сетки: A — шаг 3 px, штрихи 3 px, квадратик 2×2 (размер как сейчас, 345 px); B — шаг 2 px, штрихи 2 px,
квадратик 2×2 слитно (230 px); E — шаг 2 px, штрихи 2 px, в покое точка 1×1 (230 px, «матрица»).
  python3 tools/bootlogo_preview.py -> build/ui_shots/logo/logo_<вариант>.gif + лист logo_sheet.png"""
import re
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / 'viewer/bootlogo.h').read_text()
rows = re.findall(r'^\s*"(.*)",?\s*$', src, re.M)
H = len(rows); W = max(len(r) for r in rows)
REST, GLINT = (0x80, 0x72, 0x5A), (0xF2, 0xE6, 0xC0)
# глифы: список (dx, dy) в клетке
G = {
  'A': dict(pitch=3, g=[[(2, 0), (1, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 0), (0, 1), (1, 1)]]),
  'B': dict(pitch=2, g=[[(1, 0), (0, 1)], [(0, 0), (0, 1)], [(0, 0), (1, 1)], [(0, 0), (1, 0), (0, 1), (1, 1)]]),
  'E': dict(pitch=2, g=[[(1, 0), (0, 1)], [(0, 0), (0, 1)], [(0, 0), (1, 1)], [(0, 0)]]),
}
STAGE, SPEED, WIDTH = 4.0, 2.0, 26.0   # клеток фронта на символ, клеток за кадр (16 мс), ширина блика
def mix(a, b, t): return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
def frames(v):
    p, g = G[v]['pitch'], G[v]['g']; span = W + 2 * H; out = []
    for pas in (0, 1):
        f = -WIDTH
        while f < span + WIDTH:
            im = Image.new('RGB', (W * p + 8, H * p + 8), (0, 0, 0)); px = im.load()
            for y, r in enumerate(rows):
                for x, ch in enumerate(r):
                    if ch != '#': continue
                    d = f - (x + 2 * y)
                    if pas == 0:
                        if d < 0: continue
                        k = min(3, int(d / STAGE))
                    else:                                   # второй проход: волна символов по готовому знаку ■ → \\ → | → / → ■
                        k = 3 if d < 0 or d >= 3 * STAGE else 2 - int(d / STAGE)
                    t = min(1.0, max(0.0, d / WIDTH)) if d >= 0 else 1.0
                    c = mix(GLINT, REST, t * t) if d < WIDTH else REST
                    for dx, dy in g[k]: px[4 + x * p + dx, 4 + y * p + dy] = c
            out.append(im); f += SPEED
    return out
sheet = []
for v in G:
    fr = frames(v); big = [im.resize((im.width * 2, im.height * 2), Image.NEAREST) for im in fr]
    big[0].save(ROOT / f'build/ui_shots/logo/logo_{v}.gif', save_all=True, append_images=big[1:] + [big[-1]] * 60, duration=16, loop=0)
    mid = fr[len(fr) // 4]; fin = fr[-1]
    sheet.append((v, mid.resize((mid.width * 2, mid.height * 2), Image.NEAREST), fin.resize((fin.width * 2, fin.height * 2), Image.NEAREST)))
w = max(m.width for _, m, _ in sheet) * 2 + 30; h = sum(m.height for _, m, _ in sheet) + 20 * len(sheet)
S = Image.new('RGB', (w, h), (20, 20, 20)); y = 0
from PIL import ImageDraw
d = ImageDraw.Draw(S)
for v, m, f in sheet:
    d.text((4, y + 2), v, fill=(255, 255, 255)); S.paste(m, (20, y + 14)); S.paste(f, (30 + m.width, y + 14)); y += m.height + 20
S.save(ROOT / 'build/ui_shots/logo/logo_sheet.png'); print('кадров', len(frames('A')), '->', ROOT / 'build/ui_shots/logo')
