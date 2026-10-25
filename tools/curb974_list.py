#!/usr/bin/env python3
"""№974 «кромка у дороги»: какие куски города — бордюр. Бордюр у дороги лежит отдельными узкими длинными кусками тех же текстур тротуара (104, 110, 108, 116 …), у него нет своей текстуры.
Мак выбирает такие куски по форме и пишет curb974.bin рядом с level.shr; движок красит их как бордюр (серо-фиолетовая заливка и фрагмент асфальта), остальные куски тротуара остаются тёплыми.

  python3 tools/curb974_list.py level.shr [выход curb974.bin] [--png КАРТА.png]

Формат CB74: 'CB74', npc u32, подпись u32 (та же FNV-1a, что у flat912.bin и noise949.bin), затем npc × 1 байт: 1 — кусок-бордюр, 0 — нет.
Правило (куски текстур-заливок земли светлого нейтрального тона, как класс «тротуар» движка, без газона и асфальта): лента — меньшая сторона плана куска не больше RIB_W м, большая не меньше RIB_L м
(верх бордюра, его грань и порожек); либо тонкий по высоте (до 0,6 м) кусок шириной до RIB_W (грань)."""
import sys, struct
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flat_list as F
import shr7read as S

RIB_W, RIB_L, FACE_H = 1.25, 3.0, 0.6


def walk_class(tone):
    r, g, b = tone; mx, mn = max(r, g, b), min(r, g, b)
    return (mx - mn <= 24) and (.299 * r + .587 * g + .114 * b >= 125)


def build(lvl):
    f, tex, sig = F.load_level(lvl)
    rows = [F.classify(f, t, False) for t in tex]
    ok_tex = {i for i, r in enumerate(rows) if r[0] == 1 and tex[i]['ground'] and walk_class(r[2])}
    d = S.load(lvl); P, T, PI = d['P'], d['TEX'], d['PI']
    b = Path(lvl).read_bytes(); npc, = struct.unpack_from('<I', b, 8)
    out = bytearray(npc); pcs = []
    for pi in np.unique(PI):
        m = PI == pi; t = int(T[m][0])
        if t not in ok_tex: continue
        p = P[m].reshape(-1, 3); ex = p.max(0) - p.min(0); w, l = sorted([float(ex[0]), float(ex[2])]); h = float(ex[1])
        if (w <= RIB_W and l >= RIB_L) or (h <= FACE_H and h >= .05 and w <= RIB_W and l >= 1.0):
            out[int(pi)] = 1; pcs.append((int(pi), t, int(m.sum()), w, l, h, p.mean(0)))
    return b'CB74' + struct.pack('<II', npc, sig) + bytes(out), pcs, (d, tex, rows, ok_tex)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    lvl = a[0]; out = a[1] if len(a) > 1 else str(Path(lvl).with_name('curb974.bin'))
    data, pcs, extra = build(lvl); Path(out).write_bytes(data)
    from collections import Counter
    print(f'{lvl}: кусков-бордюров {len(pcs)} (по текстурам {dict(Counter(p[1] for p in pcs))}), длина лент {sum(p[4] for p in pcs):.0f} м -> {out}')
    if '--png' in sys.argv:
        from PIL import Image, ImageDraw
        png = sys.argv[sys.argv.index('--png') + 1]; d, tex, rows, ok_tex = extra; P, T, PI = d['P'], d['TEX'], d['PI']
        S0, X0, Z0, W = 4.0, 150.0, 100.0, 1300
        im = Image.new('RGB', (W, 1000), (30, 30, 30)); dr = ImageDraw.Draw(im); cur = {p[0] for p in pcs}
        for k in range(len(P)):
            if T[k] not in ok_tex and T[k] not in (109, 287, 111): continue
            col = (60, 160, 60) if T[k] in (109, 287) else (90, 80, 130) if T[k] == 111 else (190, 170, 120)
            if int(PI[k]) in cur: col = (255, 40, 200)
            pts = [((P[k, j, 0] - X0) * S0, (P[k, j, 2] - Z0) * S0) for j in range(3)]; dr.polygon(pts, fill=col)
        im.save(png)


if __name__ == '__main__':
    main()
