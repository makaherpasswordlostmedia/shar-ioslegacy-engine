#!/usr/bin/env python3
"""Бот-репортёр (№871): разбор CSV tools/scout/scout.c -> решение на ракурс, сводка и карты сверху (PNG).
  python3 tools/scout/report.py LEVEL_CSV OUT_PREFIX [--budget 20000]
Правило: дальность D — самая короткая из 150/200/250 м, при которой геометрия дальше D занимает ≤ 1 % экрана; порог крупной версии
FP — 90 м (Роб 23.10), 60 м — если кадр при FP 90 тяжелее бюджета (треугольников города в пирамиде, без PVS — оценка сверху)."""
import csv, sys
import numpy as np
from PIL import Image
src, pre = sys.argv[1], sys.argv[2]
budget = float(sys.argv[sys.argv.index('--budget') + 1]) if '--budget' in sys.argv else 20000.
rows = list(csv.DictReader(open(src)))
A = {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}
tot = 128 * 72
b140 = (A['px200'] + A['px250']) / tot; b200 = A['px250'] / tot   # доля экрана дальше 140 и 200 м
D = np.where(b140 <= .01, 150, np.where(b200 <= .01, 200, 250))
def tris(fp, d): return A[f'tris_fp{fp}_d{d}']
t90 = np.select([D == 150, D == 200], [tris(90, 150), tris(90, 200)], tris(90, 250))
t60 = np.select([D == 150, D == 200], [tris(60, 150), tris(60, 200)], tris(60, 250))
FP = np.where(t90 > budget, 60, 90); tsel = np.where(FP == 60, t60, t90)
base = tris(140, 200)   # как было до 23.10: FP 140, дальность 200 (тур)
n = len(rows)
print(f'{src}: ракурсов {n}')
print(f'  дальность нужна: 150 м — {100*(D==150).mean():.0f}%, 200 м — {100*(D==200).mean():.0f}%, 250 м — {100*(D==250).mean():.0f}%')
print(f'  треугольников города (оценка, медиана / 95-й процентиль): было (140/200) {np.median(base):.0f} / {np.percentile(base,95):.0f};'
      f' 90 м/200 {np.median(tris(90,200)):.0f} / {np.percentile(tris(90,200),95):.0f}; бот {np.median(tsel):.0f} / {np.percentile(tsel,95):.0f}')
print(f'  тяжелее бюджета {budget:.0f}: было {100*(base>budget).mean():.1f}% ракурсов, 90 м/200 {100*(tris(90,200)>budget).mean():.1f}%, бот {100*(tsel>budget).mean():.1f}%; FP 60 нужен в {100*(FP==60).mean():.1f}%')
# карты сверху: клетка 10 м, по точке — максимум по направлениям и высотам
x, z = A['x'], A['z']; gx = ((x - x.min()) / 10.5).astype(int); gz = ((z - z.min()) / 10.5).astype(int)
Wm, Hm = gx.max() + 1, gz.max() + 1
need = np.zeros((Hm, Wm)); load = np.zeros((Hm, Wm)); has = np.zeros((Hm, Wm), bool)
np.maximum.at(need, (gz, gx), D); np.maximum.at(load, (gz, gx), base); has[gz, gx] = True
def paint(val, cmap, out, sc=4):
    img = np.zeros((Hm, Wm, 3), np.uint8) + 24
    img[has] = cmap(val[has]); Image.fromarray(img[::-1]).resize((Wm * sc, Hm * sc), Image.NEAREST).save(out)
paint(need, lambda v: np.stack([np.where(v == 150, 70, np.where(v == 200, 230, 60)), np.where(v == 150, 200, np.where(v == 200, 180, 110)), np.where(v == 150, 90, np.where(v == 200, 60, 240))], -1).astype(np.uint8), pre + '_dal.png')
q = np.clip(load / (budget * 1.5), 0, 1)
paint(load, lambda v: (np.stack([np.clip(v / (budget * 1.5), 0, 1) * 255, (1 - np.clip(v / (budget * 1.5), 0, 1)) * 200, np.full(len(v), 40)], -1)).astype(np.uint8), pre + '_load.png')
top = np.argsort(-base)[:12]
print('  самые тяжёлые ракурсы (было -> бот): ' + '; '.join(f'({x[i]:.0f},{z[i]:.0f}) {"пешком" if A["eye"][i]==0 else "машина"} напр.{int(A["dir"][i])} {base[i]/1000:.1f}k -> {tsel[i]/1000:.1f}k D{D[i]} FP{FP[i]}' for i in top[:6]))
np.savez(pre + '_decision.npz', point=A['point'], eye=A['eye'], dir=A['dir'], D=D, FP=FP, x=x, z=z)
