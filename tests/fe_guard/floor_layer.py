#!/usr/bin/env python3
"""Гейт правки Роба 293 по данным (Мак, без эмулятора): пол гостиной — один слой, в начале перелёта NEW GAME не «ломается».
  python3 tests/fe_guard/floor_layer.py [fe.shr] [--quiet]        (по умолчанию build/fe.shr)
Красный контроль: FE_FLOOR_HID_OLD=1 python3 tools/frontend3d_export.py --out X.shr (пол в отсечении меню, как раньше) — гейт на
X.shr обязан быть красным. Проверки:
  1. у кусков пола (текстура floor3) нет флага F_MENUHID (16): движок рисует один и тот же набор кусков пола в кадре меню и в
     перелёте (у прежнего файла в первом кадре движения включались 2 куска-«двойника», FEFR тура TEST 9: floor 4 -> 6);
  2. один слой: треугольники пола попарно не накрывают друг друга (точки внутри треугольника, внутри чужого — 0; края не в счёт);
  3. набор кусков пола по кадрам начала перелёта (как в движке: главный вид — без F_MENUHID, отсечение пирамидой boxVisible) не
     меняется, пока камера не ушла;
  4. модель 16-битной глубины GE (DepthRange 65535..0, GEQUAL, очистка 0, порядок кусков файла, только непрозрачное): растр
     480×272 кадров начала перелёта (позы настоящего перелёта с PSP, TEST 9) — пиксели пола, у которых кусок-источник меняется
     между соседними кадрами не из-за сдвига камеры (у пикселя был пол одного куска — стал пол другого, и оба куска есть в обоих
     кадрах только в одном), и пиксели «на грани спора» (пол позади победителя на ≤ 2 единицы глубины: на железе шум Z ±1–2,
     docs/psp_tricks.md) — для сведения.
Код 0 — зелёный (1, 2, 3, 4 без смены источника из-за набора кусков)."""
import struct, sys, math
import numpy as np

F_ATEST, F_BLEND, F_ADD, F_NOZW, F_MENUHID = 1, 2, 4, 8, 16
TLS = [1.0, 2.124, 3.130, 4.126, 5.126, 6.128]   # TEST 9, build/psp-tour/20261004-1504/smoke.txt (FEFR), первые кадры движения


def load(path):
    d = open(path, 'rb').read()
    h = struct.unpack_from('<4s13If2I12f3I', d, 0)
    nTex, nPiece, offPiece, nTrack, offTrack, nFrames, offCam, menu, offNames = h[3], h[5], h[6], h[7], h[8], h[11], h[12], h[13], h[31]
    names = [d[offNames + 32 * i:offNames + 32 * i + 32].split(b'\0')[0].decode('latin1') for i in range(nTex)]
    tracks = [struct.unpack_from('<IIfII', d, offTrack + 32 * i) for i in range(nTrack)]
    P = []
    for i in range(nPiece):
        o = offPiece + 64 * i
        tex, ttr, fl, node, vis, _, nv, ov = struct.unpack_from('<6H2I', d, o)
        f = struct.unpack_from('<4f6f', d, o + 20)
        q = np.frombuffer(d, np.dtype([('u', '<i2'), ('v', '<i2'), ('c', '<u4'), ('x', '<i2'), ('y', '<i2'), ('z', '<i2'), ('p', '<i2')]), nv, ov)
        s = f[3] * (32768. / 32767.) / 32768.
        V = np.stack([q['x'], q['y'], q['z']], 1).astype(np.float64) * s + np.array(f[0:3])
        P.append(dict(i=i, tex=names[tex] if tex != 0xffff else '-', fl=fl, node=node, vis=vis, V=V, bb=np.array(f[4:10])))
    cam = np.frombuffer(d, '<f4', nFrames * 12, offCam).reshape(-1, 12).astype(np.float64)
    return d, P, cam, menu, tracks


def view(cam, tl):
    f0 = int(tl); f1 = min(f0 + 1, len(cam) - 1); c = cam[f0] + (cam[f1] - cam[f0]) * (tl - f0)
    return c


def node_mat(d, tracks, node, tl):
    t = tracks[node]; k = min(int(tl), t[1] - 1) if t[3] & 2 else 0   # часы гостиной стоят (кадр 0 цикла) — для модели достаточно
    r = np.frombuffer(d, '<f4', 12, t[4] + 48 * k).astype(np.float64)
    return np.array([[r[0], r[1], r[2], r[3]], [r[4], r[5], r[6], r[7]], [r[8], r[9], r[10], r[11]]])


def frame_setup(c):
    cp = c[0:3]; cf = c[3:6] / np.linalg.norm(c[3:6]); up = c[6:9]
    cr = np.cross(cf, up); cr /= np.linalg.norm(cr); cu = np.cross(cr, cf)
    tvy = math.tan(c[9] * .5) * .75; tvx = tvy * 16 / 9
    return cp, cf, cr, cu, tvx, tvy, c[10], c[11]


def box_visible(bb, R, fs):   # как frontend3d.c boxVisible
    cp, cf, cr, cu, tvx, tvy, near, far = fs
    out = [0] * 5
    for k in range(8):
        p = np.array([bb[3] if k & 1 else bb[0], bb[4] if k & 2 else bb[1], bb[5] if k & 4 else bb[2]])
        w = R[:, :3] @ p + R[:, 3] if R is not None else p
        dd = w - cp; z = dd @ cf; x = dd @ cr; y = dd @ cu
        out[0] += z < near; out[1] += x > z * tvx * 1.05; out[2] += -x > z * tvx * 1.05; out[3] += y > z * tvy * 1.05; out[4] += -y > z * tvy * 1.05
    return all(o < 8 for o in out)


def drawn(d, P, cam, menu, tracks, tl):
    c = view(cam, tl); cm = cam[menu]; home = all(abs(c[i] - cm[i]) <= 2e-3 for i in range(9)); fs = frame_setup(c)
    L = []
    for p in P:
        if p['vis'] != 0xffff: continue
        if home and p['fl'] & F_MENUHID: continue
        R = node_mat(d, tracks, p['node'], tl) if p['node'] != 0xffff else None
        if not box_visible(p['bb'], R, fs): continue
        L.append((p, R))
    return home, fs, L


def raster(L, fs):
    cp, cf, cr, cu, tvx, tvy, near, far = fs
    W, H = 480, 272
    zb = np.zeros((H, W), np.int32); idb = np.full((H, W), -1, np.int32); fz = np.zeros((H, W), np.int32)
    gx, gy = np.arange(W) + .5, np.arange(H) + .5
    A = (far + near) / (near - far); B = 2 * far * near / (near - far)   # проекция sceGumPerspective (z_ndc = (A·z + B) / -z)
    skipped = 0
    for p, R in L:
        if p['fl'] & (F_BLEND | F_ADD): continue
        V = p['V'] if R is None else (R[:, :3] @ p['V'].T).T + R[:, 3]
        rel = V - cp; z = rel @ cf; x = rel @ cr; y = rel @ cu
        floor = p['tex'].startswith('floor3')
        for k in range(0, len(V), 3):
            zz = z[k:k + 3]
            if (zz <= near).any(): skipped += 1; continue   # пересекает ближнюю — у GE режется; в модели не рисуем (вне кадра)
            sx = W / 2 + x[k:k + 3] / zz / tvx * W / 2; sy = H / 2 - y[k:k + 3] / zz / tvy * H / 2
            x0, x1 = max(0, int(sx.min())), min(W - 1, int(math.ceil(sx.max()))); y0, y1 = max(0, int(sy.min())), min(H - 1, int(math.ceil(sy.max())))
            if x0 > x1 or y0 > y1: continue
            X, Y = np.meshgrid(gx[x0:x1 + 1], gy[y0:y1 + 1])
            dd = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
            if abs(dd) < 1e-12: continue
            l1 = ((X - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (Y - sy[0])) / dd
            l2 = ((sx[1] - sx[0]) * (Y - sy[0]) - (X - sx[0]) * (sy[1] - sy[0])) / dd
            l0 = 1 - l1 - l2; m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not m.any(): continue
            iz = l0 / zz[0] + l1 / zz[1] + l2 / zz[2]                       # 1/z линейна в экране
            zv = 1. / iz; zn = (A * (-zv) + B) / zv                         # z_ndc в -1..1 (ближняя -1)
            dep = np.clip(np.round(32767.5 - 32767.5 * zn), 0, 65535).astype(np.int32)   # DepthRange(65535, 0)
            sub = zb[y0:y1 + 1, x0:x1 + 1]; ids = idb[y0:y1 + 1, x0:x1 + 1]
            win = m & (dep >= sub)                                          # GEQUAL
            sub[win] = dep[win]; ids[win] = p['i']
            if floor:
                fsub = fz[y0:y1 + 1, x0:x1 + 1]; fsub[m] = np.maximum(fsub[m], dep[m])
    return zb, idb, fz, skipped


def main():
    path = next((a for a in sys.argv[1:] if a.endswith('.shr')), 'build/fe.shr')
    d, P, cam, menu, tracks = load(path)
    fl = [p for p in P if p['tex'].startswith('floor3')]
    floor_ids = {p['i'] for p in fl}
    ok = True; why = []
    hid = [p['i'] for p in fl if p['fl'] & F_MENUHID]
    print(f'{path}: кусков пола {len(fl)}, с F_MENUHID {len(hid)} {hid if hid else ""}; треугольников пола {sum(len(p["V"]) // 3 for p in fl)}')
    if hid: ok = False; why.append(f'куски пола с F_MENUHID: {hid}')
    # 2. один слой
    T = [p['V'][k:k + 3] for p in fl for k in range(0, len(p['V']), 3)]
    ys = np.concatenate([t[:, 1] for t in T]); rng = np.random.default_rng(7); worst = 0.
    for a, ta in enumerate(T):
        w = rng.dirichlet([1, 1, 1], 600); S = w @ ta[:, [0, 2]]; cov = np.zeros(len(S), bool)
        for b, tb in enumerate(T):
            if a == b: continue
            p0, p1, p2 = tb[:, [0, 2]]
            dd = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
            if abs(dd) < 1e-12: continue
            l1 = ((S[:, 0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (S[:, 1] - p0[1])) / dd
            l2 = ((p1[0] - p0[0]) * (S[:, 1] - p0[1]) - (S[:, 0] - p0[0]) * (p1[1] - p0[1])) / dd
            cov |= (l1 > 1e-6) & (l2 > 1e-6) & (1 - l1 - l2 > 1e-6)
        worst = max(worst, cov.mean())
    print(f'один слой: высота пола {ys.min():+.4f}..{ys.max():+.4f} м; наибольшая доля треугольника пола под другим треугольником пола {worst * 100:.2f} %')
    if worst > 0: ok = False; why.append(f'наложение треугольников пола {worst * 100:.2f} %')
    # 3. набор кусков пола по кадрам начала перелёта
    sets = []
    for tl in TLS:
        home, fs, L = drawn(d, P, cam, menu, tracks, tl)
        sets.append((tl, home, fs, L, sorted(p['i'] for p, _ in L if p['i'] in floor_ids)))
    print('куски пола по кадрам (как в движке): ' + '; '.join(f"{tl:.3f}{' меню' if home else ''}: {len(s)} {s}" for tl, home, fs, L, s in sets))
    if any(s != sets[0][4] for *_, s in sets): ok = False; why.append('набор кусков пола меняется в начале перелёта')
    # 4. модель 16-битной глубины
    prev = None; switch_total = 0
    for tl, home, fs, L, s in sets:
        zb, idb, fz, skipped = raster(L, fs)
        isf = np.isin(idb, list(floor_ids))
        top_nf = (~isf) & (idb >= 0) & (fz > 0)
        near2 = int((top_nf & (zb - fz <= 2)).sum())
        line = f'  кадр {tl:.3f}{" (меню)" if home else ""}: пол на экране {int(isf.sum())} пикс; пол позади предметов на ≤ 2 ед. глубины {near2} пикс'
        if prev is not None:
            pidb, pisf, pset = prev
            both = isf & pisf; chg = both & (idb != pidb)
            # смена источника «из-за набора»: новый кусок пикселя не рисовался в прошлом кадре или прежний не рисуется в этом
            setnow = set(s); bad = chg & (np.isin(idb, list(setnow - set(pset))) | np.isin(pidb, list(set(pset) - setnow)))
            switch_total += int(bad.sum())
            line += f'; пол-пол с другим куском {int(chg.sum())} пикс (сдвиг камеры), из них из-за включения/выключения кусков {int(bad.sum())}'
        print(line)
        prev = (idb, isf, s)
    if switch_total: ok = False; why.append(f'пиксели пола меняют кусок-источник из-за набора кусков: {switch_total}')
    print('ЗЕЛЁНЫЙ' if ok else 'КРАСНЫЙ: ' + '; '.join(why))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
