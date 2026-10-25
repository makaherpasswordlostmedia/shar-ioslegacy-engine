#!/usr/bin/env python3
"""№949 «зерно шума земли одного размера в метрах». Шум земли (№912, toonflat.h) кладётся по родным UV куска; у газона и бордюров родная текстура растянута на десятки метров,
и шум растягивается вместе с ней в крупные пятна («как мокрые лужи»). Мак считает по каждому куску с шумом, сколько метров мира приходится на единицу UV (тайл) по u и по v
(медиана по площади треугольников куска, якобиан UV -> мир), и пишет noise949.bin рядом с level.shr; движок перед куском ставит sceGuTexScale так, чтобы тайл шума был P метров.

  python3 tools/noise949_list.py level.shr [выход noise949.bin]        (нужен flat912.bin-решение: куски с шумом = заливка земли, как в tools/flat_list.py)

Формат NZ49: 'NZ49', npc u32, подпись u32 (FNV-1a по номерам текстур кусков, как у flat912.bin), затем npc × 2 байта {u, v}: 0 — шума нет или не посчитано (родной масштаб),
иначе код b = round((log2(метров на тайл) + 4) * 16) + 1, 1..255 (метры = 2^((b - 1) / 16 - 4), от 6 см до 65 км, шаг 4,4 %)."""
import sys, struct, math, os
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flat_list as F
import shr7read as S

BAD_FL = 1 | 2 | 4 | (1 << 24)

def wmedian(x, w):
    o = np.argsort(x); c = np.cumsum(w[o]); return float(x[o][min(np.searchsorted(c, c[-1] * .5), len(x) - 1)])

def code(m):
    return int(max(1, min(255, round((math.log2(max(m, 1e-3)) + 4) * 16) + 1)))

def decode(b):
    return 2.0 ** ((b - 1) / 16 - 4)

def tri_periods(path):
    """-> dict(d=S.load, area, Lu, Lv, ok): метры на единицу UV по u и по v для каждого треугольника"""
    d = S.load(path); P, UV = d['P'], d['UV']
    wrap = lambda x: (x + 128.0) % 256.0 - 128.0
    e1 = P[:, 1] - P[:, 0]; e2 = P[:, 2] - P[:, 0]
    d1 = wrap(UV[:, 1] - UV[:, 0]); d2 = wrap(UV[:, 2] - UV[:, 0])
    det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    area = np.linalg.norm(np.cross(e1, e2), axis=1) * .5
    ok = (np.abs(det) > 1e-9) & (area > 1e-6)
    dd = np.where(ok, det, 1.0)
    a = d2[:, 1] / dd; b = -d1[:, 1] / dd; c = -d2[:, 0] / dd; e = d1[:, 0] / dd
    gu = a[:, None] * e1 + b[:, None] * e2; gv = c[:, None] * e1 + e[:, None] * e2
    return d, area, np.linalg.norm(gu, axis=1), np.linalg.norm(gv, axis=1), ok

def build(lvl, notoon=None):
    """-> (байты noise949.bin, список кусков dict(pi, tex, fl, area, Lu, Lv, bu, bv), nz множество текстур с шумом, sig, tri(d, area, Lu, Lv, ok))"""
    flat, rows, sig = F.build(lvl, notoon)
    f, tex, _ = F.load_level(lvl)
    noisetex = {i for i, (k, why) in enumerate(rows) if k == 1 and tex[i]['ground']}
    d, area, Lu, Lv, ok = tri_periods(lvl)
    b = Path(lvl).read_bytes(); npc, = struct.unpack_from('<I', b, 8)
    pieces = []; per = {}
    for pi in np.unique(d['PI']):
        m = d['PI'] == pi; t = int(d['TEX'][m][0]); fl = int(d['FL'][m][0])
        if t not in noisetex or (fl & BAD_FL): continue
        mm = m & ok
        if not mm.any(): continue
        w = area[mm]; lu, lv = wmedian(Lu[mm], w), wmedian(Lv[mm], w)
        pieces.append(dict(pi=int(pi), tex=t, fl=fl, area=float(w.sum()), Lu=lu, Lv=lv))
        per.setdefault(t, []).append((lu, lv, float(w.sum())))
    # куски без посчитанного UV (вырожденные): медиана текстуры
    ptab, = struct.unpack_from('<I', b, 76); have = {p['pi'] for p in pieces}
    for pi in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * pi); t, fl, own = r[6], r[7], r[10]
        if own != 0 or t not in noisetex or (fl & BAD_FL) or pi in have or t not in per: continue
        pw = per[t]; lu = wmedian(np.array([x[0] for x in pw]), np.array([x[2] for x in pw])); lv = wmedian(np.array([x[1] for x in pw]), np.array([x[2] for x in pw]))
        pieces.append(dict(pi=pi, tex=t, fl=fl, area=0.0, Lu=lu, Lv=lv))
    body = bytearray(2 * npc)
    for p in pieces:
        p['bu'], p['bv'] = code(p['Lu']), code(p['Lv']); body[2 * p['pi']] = p['bu']; body[2 * p['pi'] + 1] = p['bv']
    return b'NZ49' + struct.pack('<II', npc, sig) + bytes(body), pieces, noisetex, sig, (d, area, Lu, Lv, ok)

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    lvl = a[0]; out = a[1] if len(a) > 1 else str(Path(lvl).with_name('noise949.bin'))
    data, pieces, nz, sig, _ = build(lvl); Path(out).write_bytes(data)
    print(f'{lvl}: кусков с шумом {len(pieces)}, текстур {len(nz)}, подпись {sig:08x} -> {out}')

if __name__ == '__main__':
    main()
