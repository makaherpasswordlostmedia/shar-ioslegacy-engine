#!/usr/bin/env python3
# №965: блик монет — размер и центр по снимкам. Три сборки с одинаковым кадром (эмулятор повторяет числа): none (блик погашен, -DCOIN_GLINT_S=0.001f) — только монета;
# new / old — с бликом. Блик = разница снимка с none (сумма каналов > 12). Монета = оранжевые пиксели none-снимка у центра блика (окно столбцов 150..330: камера смотрит в центр монеты).
#   check.py gate NONE_DIR OLD_DIR NEW_DIR      ширина блика new ≤ 0,62 от old и ≥ 0,25 (не исчез); центр блика в пределах 0,2 ширины монеты от центра монеты; нижняя/верхняя половины блика по массе 0,6..1,7
#   check.py same A_DIR B_DIR NAME...           снимки NAME одинаковы пиксель в пиксель (соседние блики не тронуты)
import sys, os
from PIL import Image
import numpy as np
def load(d, n): return np.asarray(Image.open(os.path.join(d, n + '.png')).convert('RGB')).astype(int)
def glint(none, img):
    m = np.abs(img - none).sum(axis=2) > 12; m[:60, :] = False; m[:, :150] = False; m[:, 330:] = False   # без полосы HUD; монета, на которую смотрит камера, — по центру экрана (соседние монеты вне окна)
    return m
def coin_mask(none, gm):
    ys, xs = np.nonzero(gm)
    if len(xs) < 20: return None
    cx, cy = int(np.median(xs)), int(np.median(ys))
    r, g, b = none[..., 0], none[..., 1], none[..., 2]
    c = (r > 150) & (r - g > 55) & (g - b > -10) & (g < 175) & (b < 120)
    box = np.zeros_like(c); box[max(60, cy - 70):cy + 70, max(0, cx - 70):cx + 70] = True
    c &= box
    # самая крупная связная часть (без scipy: заливка от пикселя, ближайшего к медиане блика)
    yy, xx = np.nonzero(c)
    if len(xx) < 50: return None
    i = np.argmin((xx - cx) ** 2 + (yy - cy) ** 2); seen = np.zeros_like(c); st = [(yy[i], xx[i])]; seen[yy[i], xx[i]] = True
    while st:
        y, x = st.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            Y, X = y + dy, x + dx
            if 0 <= Y < c.shape[0] and 0 <= X < c.shape[1] and c[Y, X] and not seen[Y, X]: seen[Y, X] = True; st.append((Y, X))
    return seen
def stats(none, img):
    gm = glint(none, img); cm = None
    if gm.sum() < 20: return None
    # монета — по none-снимку; её центр — центр рамки монеты
    cm = coin_mask(none, gm)
    if cm is None: return None
    ys, xs = np.nonzero(cm); cw = xs.max() - xs.min() + 1; ch = ys.max() - ys.min() + 1; ccx = (xs.max() + xs.min()) / 2; ccy = (ys.max() + ys.min()) / 2
    gy, gx = np.nonzero(gm); w = np.asarray(np.abs(img - none).sum(axis=2))[gy, gx].astype(float)
    gcx = (gx * w).sum() / w.sum(); gcy = (gy * w).sum() / w.sum()
    up = w[gy < ccy].sum(); dn = w[gy >= ccy].sum()
    return dict(gw=gx.max() - gx.min() + 1, gh=gy.max() - gy.min() + 1, cw=cw, ch=ch, dx=(gcx - ccx) / cw, dy=(gcy - ccy) / ch, ud=dn / max(up, 1.0), mass=w.sum())
def gate(nd, od, wd):
    bad = 0; rows = []
    for L in ('l1', 'l2', 'l5'):
        for k in 'abcd':
            n = 'k_%s_%s' % (L, k)
            try: none = load(nd, n); so = stats(none, load(od, n)); sn = stats(none, load(wd, n))
            except Exception as e: print('нет снимка', n, e); bad += 1; continue
            if not so or not sn: print(n, 'блик не найден: old=%s new=%s' % (bool(so), bool(sn))); bad += 1; continue
            rows.append((L, k, so, sn))
            print('%s: ширина блика old %d new %d (монета %d); центр new dx=%+.2f dy=%+.2f (old dx=%+.2f dy=%+.2f); низ/верх new %.2f old %.2f' % (n, so['gw'], sn['gw'], sn['cw'], sn['dx'], sn['dy'], so['dx'], so['dy'], sn['ud'], so['ud']))
    if not rows: print('FAIL: нет данных'); return 1
    rs = sorted(r[3]['gw'] / r[2]['gw'] for r in rows); ratio = rs[len(rs) // 2]
    dxs = sorted(abs(r[3]['dx']) for r in rows); dys = sorted(abs(r[3]['dy']) for r in rows); uds = sorted(r[3]['ud'] for r in rows)
    med = lambda a: a[len(a) // 2]
    print('медианы: ширина new/old %.2f; |dx| %.2f |dy| %.2f (доли монеты); низ/верх %.2f' % (ratio, med(dxs), med(dys), med(uds)))
    if not .25 <= ratio <= .62: print('BAD: размер блика не вдвое меньше (ждём .25..0,62)'); bad += 1
    if med(dxs) > .2 or med(dys) > .2: print('BAD: центр блика не в центре монеты (>0,2 размера)'); bad += 1
    if not .6 <= med(uds) <= 1.7: print('BAD: блик съехал вверх или вниз (масса низ/верх вне 0,6..1,7)'); bad += 1
    return bad
def orange(img):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    return (r > 150) & (r - g > 55) & (g > 30) & (g < 175) & (b < 120)
def near(mask, rad):   # расширение маски квадратом rad пикселей (без scipy)
    out = mask.copy()
    for dy in range(-rad, rad + 1, 4):
        for dx in range(-rad, rad + 1, 4):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out
def same(a, b, names, coins=False):
    # строка HUD (y < 60: счётчик кадров) не считается; coins — отличия вблизи оранжевых монет разрешены (это и есть правка), всё остальное — пиксель в пиксель
    bad = 0
    for n in names:
        try: x = load(a, n); y = load(b, n)
        except Exception as e: print('нет снимка', n, e); bad += 1; continue
        d = np.abs(x - y).sum(axis=2) > 0; d[:60, :] = False
        tot = int(d.sum())
        if coins: d &= ~near(orange(x) | orange(y), 32)
        out = int(d.sum())
        print('%s: отличающихся пикселей %d%s' % (n, out, (' (у монет ещё %d, разрешено)' % (tot - out)) if coins else ''))
        if out: bad += 1
    return bad
if __name__ == '__main__':
    m = sys.argv[1]
    bad = gate(*sys.argv[2:5]) if m == 'gate' else same(sys.argv[2], sys.argv[3], [n for n in sys.argv[4:] if n != '--coins'], '--coins' in sys.argv)
    print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
