#!/usr/bin/env python3
"""№684: размер картинки машины в будке (кадры smoke c0..c5 страницы PhoneBooth, 480×272).
   booth684_check.py OLD_DIR NEW_DIR   — OLD_DIR: кадры прежнего пакета (BOOTH_CAR_SCALE_OLD=1), NEW_DIR: кадры нового.
   Зелёное: высота машины на каждом кадре новая/старая ≈ 0,85 (0,80–0,90); красный контроль: OLD против OLD даёт 1,00 и гейт падает.
   Машина = пиксели области галереи (x 34..224, y 66..236), заметно отличающиеся от фона и не жёлтые/белые подписи замка."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def car_bbox(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)
    g = a[66:236, 34:224]                             # галерея под названием машины (низ имени — строка 62), между стрелками; с 92 обрезался верх высоких машин (Canyonero)
    top = g[1:4].mean(0); bot = g[-4:-1].mean(0)      # фон: линейно от верхней строки области к нижней, по каждому столбцу
    t = np.linspace(0, 1, g.shape[0])[:, None, None]
    bg = top[None] * (1 - t) + bot[None] * t
    d = np.abs(g - bg).sum(-1)
    white = (g.min(-1) > 200)                         # подпись LEVEL N у замка
    yellow = (g[..., 0] > 200) & (g[..., 1] > 150) & (g[..., 2] < 90)   # замок
    m = (d > 45) & ~white & ~yellow
    ys, xs = np.where(m)
    if len(ys) < 200:
        return None
    return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())


def main(old, new, lo=0.80, hi=0.90):
    old, new = Path(old), Path(new)
    fails, rows = [], []
    for i in range(6):
        a, b = car_bbox(old / f'c{i}.png'), car_bbox(new / f'c{i}.png')
        if not a or not b:
            fails.append(f'c{i}: машина не найдена'); continue
        ha, hb = a[1] - a[0] + 1, b[1] - b[0] + 1; wa, wb = a[3] - a[2] + 1, b[3] - b[2] + 1
        r = hb / ha; rw = wb / wa
        rows.append((i, ha, hb, wa, wb, r, rw))
        if not (lo <= r <= hi and lo <= rw <= hi):
            fails.append(f'c{i}: высота {ha}→{hb} (×{r:.2f}), ширина {wa}→{wb} (×{rw:.2f}), ждали {lo}–{hi}')
    for i, ha, hb, wa, wb, r, rw in rows:
        print(f'  c{i}: высота {ha}→{hb} ×{r:.2f}, ширина {wa}→{wb} ×{rw:.2f}')
    if fails:
        print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; return 1
    print('OK: картинки машин в будке ×0,85 по обеим осям, пропорции сохранены'); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
