#!/usr/bin/env python3
"""Перепись семейства «стена выше крыши» (правка Роба 47: «часть домов — стена до неба, прозрачная»). Только чтение level.shr.
  python3 tools/cartest/tallwalls.py [--level build/level.shr] [--top 15]   -> сводка в stdout + build/sandbox/tallwalls-<время>.json
Что считает (всё по COL1 и рисуемым кускам города того же файла):
  заборы Wall 0x3000000  — у забора в данных нет высоты (концы y = 0); граница карты = за забором (2 м по -n) нет опоры
                           коллизии; внутренний = опора есть. Для каждого: верх (y1; 1e6 — «до неба») и насколько он выше
                           видимого и опоры в полосе ±1.5 м. До 29.09 все были «до неба»; правило — tools/psp_export.py
                           col_fence_tops (внутренние — до верха видимого + 1 м, не ниже опоры + 4 м; границы как были)
  ящики/цилиндры COL1    — верх объёма против верха нарисованного в его следе: на сколько коллизия выше картинки
                           (двускатная крыша, закрытая ящиком по коньку, — стенка над свесом; данные диска, не правим)
Повтор проблемного места: tests/jumps/host.sh (перелёт дома jumpzone17: удары в полёте выше нарисованного)."""
import argparse, json, struct, time, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]


def load(path):
    b = Path(path).read_bytes()
    npc, = struct.unpack_from('<I', b, 8); tableOff, = struct.unpack_from('<I', b, 76); cellOff, = struct.unpack_from('<I', b, 84)
    co, = struct.unpack_from('<I', b, 92)
    hdr = struct.unpack_from('<4s3f8I', b, co); ntri, nbox, ncyl, nseg = hdr[6:10]
    o = co + 48
    tri = np.frombuffer(b, '<f4', 12 * ntri, o).reshape(-1, 4, 3); o += 48 * ntri
    box = np.frombuffer(b, '<f4', 16 * nbox, o).reshape(-1, 16); o += 64 * nbox
    cyl = np.frombuffer(b, '<f4', 12 * ncyl, o).reshape(-1, 12); o += 48 * ncyl
    seg = np.frombuffer(b, '<f4', 8 * nseg, o).reshape(-1, 8)
    T = []
    for i in range(npc):
        r = struct.unpack_from('<6fi4I4f3I2I', b, tableOff + 80 * i)
        fl, nv, ni, owner = r[7:11]; rox, roy, roz, sc = r[11:15]; off, cel = r[15], r[17]
        if owner != 0 or (fl & 4) or not (fl & 16): continue
        vs = 12 if (fl & 32) else 16; base = struct.unpack_from('<6f6I', b, cellOff + 48 * cel)[9] + off
        raw = np.frombuffer(b, np.uint8, ni * vs, base).reshape(ni, vs); p0 = 6 if vs == 12 else 8
        q = raw[:, p0:p0 + 6].copy().view('<i2').reshape(ni, 3).astype(np.float32) * (sc / 32768)
        n3 = ni // 3 * 3
        T.append((q[:n3] + [rox, roy, roz]).reshape(-1, 3, 3))
    return dict(tri=tri, box=box, cyl=cyl, seg=seg, render=np.concatenate(T))


def grid_max(P, lo, W, H, cell):
    G = np.full((H, W), -1e9, np.float32)
    ext = np.max([np.linalg.norm(P[:, (i + 1) % 3] - P[:, i], axis=1) for i in range(3)], 0)
    ns = np.clip(np.ceil(ext / (cell * .5)).astype(int), 1, 300)
    for n in np.unique(ns):
        S = P[ns == n]; us = np.arange(n + 1) / n; uu, vv = np.meshgrid(us, us); m = uu + vv <= 1 + 1e-6; uu, vv = uu[m], vv[m]
        for k0 in range(0, len(uu), 32):
            u = uu[k0:k0 + 32][None, :, None]; v = vv[k0:k0 + 32][None, :, None]
            Q = (S[:, None, 0] * (1 - u - v) + S[:, None, 1] * u + S[:, None, 2] * v).reshape(-1, 3)
            ix = ((Q[:, 0] - lo[0]) / cell).astype(np.int64); iz = ((Q[:, 2] - lo[1]) / cell).astype(np.int64)
            ok = (ix >= 0) & (ix < W) & (iz >= 0) & (iz < H)
            np.maximum.at(G, (iz[ok], ix[ok]), Q[ok, 1])
    return G


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=Path, default=ROOT / 'build/level.shr'); ap.add_argument('--top', type=int, default=15)
    a = ap.parse_args()
    L = load(a.level); cell = 1.5
    allp = np.concatenate([L['render'].reshape(-1, 3), L['tri'][:, :3].reshape(-1, 3)])
    lo = allp[:, [0, 2]].min(0) - 5; hi = allp[:, [0, 2]].max(0) + 5
    W, H = int((hi[0] - lo[0]) / cell) + 1, int((hi[1] - lo[1]) / cell) + 1
    VG = grid_max(L['render'].astype(np.float32), lo, W, H, cell)
    TR = L['tri'][:, :3].astype(np.float32); walk = L['tri'][:, 3, 1] > .5
    GG = grid_max(TR[walk], lo, W, H, cell)
    def cells(x, z):
        gx = np.floor((x - lo[0]) / cell).astype(np.int64); gz = np.floor((z - lo[1]) / cell).astype(np.int64)
        ok = (gx >= 0) & (gx < W) & (gz >= 0) & (gz < H); return gx.clip(0, W - 1), gz.clip(0, H - 1), ok
    fences = []
    for i, s in enumerate(L['seg']):
        a0, b0, n = s[0:2], s[2:4], s[4:6]; ln = float(np.hypot(*(b0 - a0))); u = np.linspace(0, 1, max(2, int(np.ceil(ln)) + 1))
        P = a0 + (b0 - a0) * u[:, None]
        gx, gz, ok = cells(P[:, 0] - n[0] * 2, P[:, 1] - n[1] * 2); behind = (ok & (GG[gz, gx] > -1e8)).mean()
        off = np.linspace(-1.5, 1.5, 5); X = (P[:, None, 0] + n[0] * off).ravel(); Z = (P[:, None, 1] + n[1] * off).ravel()
        cx, cz, ok2 = cells(X, Z); vt = float(VG[cz[ok2], cx[ok2]].max()) if ok2.any() else -1e9; gt = float(GG[cz[ok2], cx[ok2]].max()) if ok2.any() else -1e9
        fences.append(dict(i=i, len=round(ln, 1), bound=bool(behind <= .5), y1=float(s[7]), vis=round(vt, 1), ground=round(gt, 1),
                           over=round(float(s[7]) - max(vt, gt), 1) if s[7] < 1e5 and max(vt, gt) > -1e8 else None,
                           at=[round(float(v), 1) for v in (a0 + b0) / 2]))
    boxes = []
    B = L['box']; ax = B[:, 3:12].reshape(-1, 3, 3); h = B[:, 12:15]; top = B[:, 1] + (np.abs(ax[:, :, 1]) * h).sum(1)
    ex_ = (np.abs(ax[:, :, 0]) * h).sum(1); ez_ = (np.abs(ax[:, :, 2]) * h).sum(1)
    for i in range(len(B)):
        cx0, cz0, _ = cells(np.array([B[i, 0] - ex_[i]]), np.array([B[i, 2] - ez_[i]])); cx1, cz1, _ = cells(np.array([B[i, 0] + ex_[i]]), np.array([B[i, 2] + ez_[i]]))
        v = VG[cz0[0]:cz1[0] + 1, cx0[0]:cx1[0] + 1]; vt = float(v.max()) if v.size else -1e9
        if vt < -1e8: continue   # в следе ничего не нарисовано (объект рисует SPR1/ANM1) — не про крыши
        boxes.append(dict(i=i, top=round(float(top[i]), 1), vis=round(vt, 1), over=round(float(top[i]) - vt, 1), at=[round(float(B[i, 0]), 1), round(float(B[i, 2]), 1)]))
    inner = [f for f in fences if not f['bound']]; bound = [f for f in fences if f['bound']]
    sky_inner = [f for f in inner if f['y1'] > 1e5]
    res = dict(level=str(a.level), fences=len(fences), bound=len(bound), inner=len(inner), innerToSky=len(sky_inner),
               innerOverVisible=dict(median=float(np.median([f['over'] for f in inner if f['over'] is not None] or [0]))),
               boxesOver1m=sum(b['over'] > 1 for b in boxes), boxesOver3m=sum(b['over'] > 3 for b in boxes),
               topBoxes=sorted(boxes, key=lambda b: -b['over'])[:a.top], topSkyInner=sorted(sky_inner, key=lambda f: -f['len'])[:a.top])
    out = ROOT / 'build/sandbox' / f'tallwalls-{time.strftime("%Y%m%d-%H%M%S")}.json'; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f'заборы: {len(fences)} кусков; граница карты (за ними пустота, «до неба» по закону 3) {len(bound)}; внутренних {len(inner)}, '
          f'из них «до неба» {len(sky_inner)}; внутренние выше видимого/опоры в полосе ±1.5 м: медиана {res["innerOverVisible"]["median"]:.1f} м')
    print(f'ящики COL1 выше нарисованного в своём следе: на 1+ м {res["boxesOver1m"]}, на 3+ м {res["boxesOver3m"]} (данные диска, не правим)')
    for b in res['topBoxes'][:5]: print(f'   ящик #{b["i"]} ({b["at"][0]}, {b["at"][1]}): верх {b["top"]}, нарисовано {b["vis"]}, выше на {b["over"]}')
    print('->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
