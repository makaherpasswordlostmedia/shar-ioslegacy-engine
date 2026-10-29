#!/usr/bin/env python3
"""Гейт правки 366 (горизонт: штрихи и строки пикселей над горами): синтетическая полоса гор RGBA 128×64 с мягким краем силуэта
(как l1_BACKMOUNTAINS: альфа-тест GREATER 0x40), без данных игры. tools/texq.build -> decode; на каждом уровне (с мипами до 1 px,
SMALL_MIPS + PRESWIZZLE, как ship) сравниваем «проходит / не проходит» тест 0x40 у эталона уровня и у тексела из палитры:
  ложный проход — эталон ≤ 0x40, а записанный цвет > 0x40 (штрих над горами); ложный провал — наоборот (дырка в горах).
Зелёный: 0 и 0 на всех уровнях. Красный: SHR_ALPHA_NEAREST_OLD=1 (прежний подбор) обязан дать ложные проходы.
  python3 tests/texq/alpha366.py            # красный + зелёный -> PASS / FAIL
"""
import os, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]


def mountains(w=128, h=64, seed=7):
    rng = np.random.default_rng(seed)
    x = np.arange(w)
    ridge = h * .45 + 9 * np.sin(x / 9.0) + 5 * np.sin(x / 3.7 + 1) + rng.normal(0, 1.2, w)   # верх гор, строка
    y = np.arange(h)[:, None]
    soft = 2.5                                                    # мягкий край силуэта, px
    a = np.clip((y - ridge[None]) / soft + .5, 0, 1)
    sky = np.array([150, 190, 235], np.float32)                   # цвет в прозрачной части (как на диске: небо под альфой 0)
    rock = np.stack([90 + 40 * np.sin(x / 5.0)[None].repeat(h, 0), 110 + 0 * y.repeat(w, 1), 70 + .8 * y.repeat(w, 1)], -1)
    rgb = sky[None, None] * (1 - a[..., None]) + rock * a[..., None] + rng.normal(0, 6, (h, w, 3))   # шум: > 256 цветов -> k-means
    px = np.concatenate([np.clip(rgb, 0, 255), (a * 255)[..., None]], -1)
    return Image.fromarray(np.round(px).astype(np.uint8), 'RGBA')


def run():
    sys.path.insert(0, str(ROOT / 'tools'))
    import texq
    texq.SMALL_MIPS = True
    fp = fn = 0
    # A — 32-битная картинка (k-means по всем уровням); B — 8 бит с палитрой, как на диске PS2 (уровень 0 без потерь, свободные
    # записи палитры — цветам мипов: здесь прозрачные тексели мипов и находили «соседа» с альфой 87–152)
    m = mountains(); pal8 = m.quantize(200, method=Image.Quantize.FASTOCTREE).convert('RGBA')
    for case, img in (('A 32 бит', m), ('B 8 бит с палитрой', pal8)):
        data, levels, pal, fmt = texq.build(img, cap=128, preswizzle=True)
        got = texq.decode(data); ref = texq.ALPHA_REF
        for li, (r, g) in enumerate(zip(levels, got)):
            ra = np.asarray(r, np.uint8)[..., 3] > ref; ga = g[..., 3] > ref
            p, n = int((~ra & ga).sum()), int((ra & ~ga).sum()); fp += p; fn += n
            if p or n or li < 2: print(f'  {case} уровень {li} {r.size[0]}x{r.size[1]}: ложных проходов {p}, ложных провалов {n}')
    print(f'RESULT fp={fp} fn={fn}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--one':
        run(); sys.exit(0)
    def one(old):
        env = dict(os.environ); env.pop('SHR_ALPHA_NEAREST_OLD', None)
        if old: env['SHR_ALPHA_NEAREST_OLD'] = '1'
        out = subprocess.run([sys.executable, __file__, '--one'], env=env, capture_output=True, text=True).stdout
        print(out, end=''); r = [l for l in out.splitlines() if l.startswith('RESULT')]
        return dict(kv.split('=') for kv in r[0].split()[1:]) if r else None
    print('== красный SHR_ALPHA_NEAREST_OLD=1'); red = one(True)
    print('== зелёный'); green = one(False)
    red_ok = red is not None and int(red['fp']) > 0
    green_ok = green is not None and int(green['fp']) == 0 and int(green['fn']) == 0
    print('красный:', 'пойман (ложные проходы есть)' if red_ok else 'НЕ ПОЙМАН')
    print('PASS' if red_ok and green_ok else 'FAIL', ': альфа-тест 0x40 у мипов сохраняется')
    sys.exit(0 if red_ok and green_ok else 1)
