#!/usr/bin/env python3
"""Правка Роба 265, свидетель по данным (Мак, CPU, без эмулятора): какой уровень мипа берёт пол гостиной (floor3.bmp, 256×256,
8 уровней) в перелёте NEW GAME (кадры таймлайна go0..go1 из FLT1, шаг 0,25) при разных правилах выбора.

  python3 tests/fe_guard/mip_model.py [build/fe.shr]

Модели (для каждого видимого треугольника пола после среза по near — веер, как PPSSPP Clipper):
  AUTO-пиксель  log2(max(|ds/dx|·W, |dt/dy|·H)) в каждой точке (так считает PPSSPP на квад 2×2 — эмулятор), максимум по экрану
  AUTO-вершины  то же, но одно число на треугольник — по худшей вершине
  AUTO-рамка    одно число на треугольник — в углу его рамки на экране (вне треугольника: продолжение плоскости 1/w)
  SLOPE         правило 265: log2(2·w·наклон), наклон = плотность текстуры × tvy/272 × 2^0,5 (frontend3d.c mipPick); по пикселям
  SLOPE-рамка   то же, если бы железо взяло глубину в углу рамки треугольника (худший случай)
Уровень 0 — полная текстура; у floor3 тени мебели заметны до уровня ~5 (разброс 29 из 255), на 7 (2×2) пол ровный (8 из 255).
На настоящей PSP AUTO даёт один уровень на треугольник (правки 77/88: ступеньки между треугольниками асфальта), точная точка
расчёта неизвестна — поэтому несколько моделей. Итог: «свидетель» (прежнее под риском только в моделях «на треугольник») и
«правило» (SLOPE не выше 3 даже в худшей точке). Код возврата 1, если правило в худшей точке ≥ 4 или свидетель не видит риска."""
import math, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/fe.shr'
LIFT = 0.5                                   # frontend3d.c FE_MIP_LIFT

b = FE.read_bytes()
magic, ver, size, ntex, otex, npc, opc, ntr, otr, nbl, obl, nfr = struct.unpack_from('<4s11I', b, 0)
ocam, = struct.unpack_from('<I', b, 48); onm, = struct.unpack_from('<I', b, 124)
names = [b[onm + 32 * i:onm + 32 * i + 32].rstrip(b'\0').decode('latin1') for i in range(ntex)]
cam = np.frombuffer(b, '<f4', nfr * 12, ocam).reshape(nfr, 12).astype(np.float64)
of, nf_ = struct.unpack_from('<II', b, len(b) - 12)
flights = [struct.unpack_from('<BBHHHHHf', b, of + 16 * k) for k in range(nf_)] if b[-16:-12] == b'FLT1' else []
go0, go1 = next((f[3], f[4]) for f in flights if f[0] == 4)
VT = np.dtype([('u', '<u2'), ('v', '<u2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')])
TEX = names.index('floor3.bmp'); W, H = struct.unpack_from('<HH', b, otex + 64 * TEX)
floor = []
for i in range(npc):
    t = struct.unpack_from('<6H2I4f6fI', b, opc + 64 * i)
    if t[0] != TEX or t[4] != 0xffff or t[3] != 0xffff: continue
    q = np.frombuffer(b, VT, t[6], t[7])
    P = np.stack([q['x'], q['y'], q['z']], 1).astype(np.float64) / 32767. * t[11] + np.array(t[8:11])
    UV = np.stack([q['u'], q['v']], 1).astype(np.float64) / 256.
    T = P.reshape(-1, 3, 3); U = UV.reshape(-1, 3, 2)
    wa = (np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2).sum()
    ua = (np.abs((U[:, 1, 0] - U[:, 0, 0]) * (U[:, 2, 1] - U[:, 0, 1]) - (U[:, 2, 0] - U[:, 0, 0]) * (U[:, 1, 1] - U[:, 0, 1])) / 2).sum()
    dens = math.sqrt(ua / wa) * math.sqrt(W * H)                 # тексели на метр, как frontend3d.c (pDens × sqrt(W·H))
    for k in range(len(T)): floor.append((i, k, T[k], U[k], dens))


def view(tl):
    f0 = int(tl); f1 = min(f0 + 1, nfr - 1); c = cam[f0] + (cam[f1] - cam[f0]) * (tl - f0)
    pos = c[:3]; fw = c[3:6] / np.linalg.norm(c[3:6]); r = np.cross(fw, c[6:9]); r /= np.linalg.norm(r); u = np.cross(r, fw)
    tvy = math.tan(c[9] * .5) * .75
    return pos, fw, r, u, tvy * 16 / 9, tvy, c[10]


def clip_near(V, near):
    out = []
    for i in range(len(V)):
        a, c = V[i], V[(i + 1) % len(V)]
        if a[2] >= near: out.append(a)
        if (a[2] >= near) != (c[2] >= near): out.append(a + (c - a) * ((near - a[2]) / (c[2] - a[2])))
    return out


def models(V, fx, fy, tvy, dens):
    z = V[:, 2]; sx = 240 + V[:, 0] / z * fx; sy = 136 - V[:, 1] / z * fy; s = V[:, 3] * W; t = V[:, 4] * H
    d = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
    if abs(d) < 1e-9: return None
    g = lambda a: (((a[1] - a[0]) * (sy[2] - sy[0]) - (a[2] - a[0]) * (sy[1] - sy[0])) / d, ((sx[1] - sx[0]) * (a[2] - a[0]) - (sx[2] - sx[0]) * (a[1] - a[0])) / d)
    Q = 1 / z; Sg, Tg, Qg = g(s * Q), g(t * Q), g(Q)
    val = lambda a, gg, px, py: a[0] + gg[0] * (px - sx[0]) + gg[1] * (py - sy[0])

    def auto(px, py):
        q = val(Q, Qg, px, py)
        if np.any(q <= 1e-9): return 99.
        S_, T_ = val(s * Q, Sg, px, py), val(t * Q, Tg, px, py)
        return np.log2(np.maximum(np.maximum(np.abs((Sg[0] * q - S_ * Qg[0]) / q ** 2), np.abs((Tg[1] * q - T_ * Qg[1]) / q ** 2)), 1e-9))
    slope = dens * tvy / 272 * 2 ** LIFT
    sl = lambda w: math.log2(2 * w * slope) if w > 0 else 99.
    # видимая часть: точки сетки 4 px внутри треугольника и экрана
    x0, x1, y0, y1 = max(sx.min(), 0), min(sx.max(), 480), max(sy.min(), 0), min(sy.max(), 272)
    if x0 >= x1 or y0 >= y1: return None
    gx, gy = np.meshgrid(np.arange(x0, x1, 4.) + 2, np.arange(y0, y1, 4.) + 2)
    l1 = ((gx - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (gy - sy[0])) / d; l2 = ((sx[1] - sx[0]) * (gy - sy[0]) - (gx - sx[0]) * (sy[1] - sy[0])) / d
    m = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
    if not m.any(): return None
    px, py = gx[m], gy[m]
    w_pix = 1 / val(Q, Qg, px, py)
    qtl = val(Q, Qg, sx.min(), sy.min())
    return dict(pix=float(np.max(auto(px, py))), vtx=float(max(auto(sx[i], sy[i]) for i in range(3))), box=float(auto(sx.min(), sy.min())),
                slope=float(max(sl(w) for w in (w_pix.min(), w_pix.max()))), slope_box=sl(1 / qtl) if qtl > 1e-9 else 99., px=int(m.sum()) * 16)


def main():
    keys = ['pix', 'vtx', 'box', 'slope', 'slope_box']
    print(f'fe.shr {FE} ({len(b)} Б): пол floor3.bmp {W}×{H}, треугольников {len(floor)}, NEW GAME кадры {go0}..{go1}')
    print(' кадр  треуг  AUTO-пиксель AUTO-вершины AUTO-рамка  SLOPE SLOPE-рамка   (наибольший уровень по видимым треугольникам пола; '
          'отрицательное = 0)')
    worst = {k: (-99, 0) for k in keys}; risk = []
    for tl in np.arange(go0, go1 + 1e-6, .25):
        pos, fw, r, u, tvx, tvy, near = view(tl); fx, fy = 240 / tvx, 136 / tvy
        mx = {k: -99. for k in keys}; n = 0
        for i, k, T, U, dens in floor:
            rel = T - pos; V = np.c_[rel @ r, rel @ u, rel @ fw, U]
            x, y, z = V[:, 0], V[:, 1], V[:, 2]
            if (z < near).all() or (x > z * tvx).all() or (-x > z * tvx).all() or (y > z * tvy).all() or (-y > z * tvy).all(): continue
            cp = np.array(clip_near(list(V), near))
            for j in range(1, len(cp) - 1):
                mm = models(cp[[0, j, j + 1]], fx, fy, tvy, dens)
                if not mm: continue
                n += 1
                for kk in keys: mx[kk] = max(mx[kk], mm[kk])
        for kk in keys:
            if mx[kk] > worst[kk][0]: worst[kk] = (mx[kk], tl)
        if mx['box'] >= 3 or mx['vtx'] >= 3: risk.append(round(float(tl), 2))
        if abs(tl * 2 - round(tl * 2)) < 1e-6:
            print(f'{tl:5.2f} {n:5d}  ' + '  '.join(f'{mx[kk]:10.2f}' for kk in keys))
    print('наибольшее за перелёт: ' + ', '.join(f'{kk} {worst[kk][0]:.2f} (кадр {worst[kk][1]:.2f})' for kk in keys))
    print(f'свидетель: прежнее AUTO «на треугольник» даёт уровень ≥ 3 в подкадрах {risk[:20]}{" …" if len(risk) > 20 else ""} '
          f'(всего {len(risk)} из {len(np.arange(go0, go1 + 1e-6, .25))}); AUTO по пикселям (эмулятор) — не выше {worst["pix"][0]:.2f}')
    ok_rule = worst['slope_box'][0] < 4 and worst['slope'][0] < 1
    ok_wit = len(risk) > 0
    print(f'правило: SLOPE по пикселям не выше {worst["slope"][0]:.2f}, в худшей точке (угол рамки) не выше {worst["slope_box"][0]:.2f}')
    print('ИТОГ:', 'зелёный' if ok_rule and ok_wit else 'КРАСНЫЙ', '' if ok_wit else '(свидетель не видит риска — версия не подтверждается данными)')
    return 0 if ok_rule and ok_wit else 1


if __name__ == '__main__':
    sys.exit(main())
