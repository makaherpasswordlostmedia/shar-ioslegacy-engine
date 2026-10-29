#!/usr/bin/env python3
"""№863/№864 (Роб 23.10: «L3 проседает — что за полупрозрачные куски»; «пропечь заранее на компьютере»): список кусков города,
помеченных полупрозрачными (флаг 2), у которых прозрачности нет вовсе — альфа всех вершин ближней и дальней версии >= OPQ_A
и вся картинка уровня 0 непрозрачна. Главный случай — море L3/L6 (текстура волн, 45 тыс. треугольников): как полупрозрачное оно
не попадало в листы клеток, сортировалось и рисовалось по куску. Движок при загрузке уровня снимает флаг 2 с этих кусков
(viewer/main_levels.h, opq863Apply), если подпись таблицы кусков совпала. Данные уровня не меняются.

  python3 tools/opq863.py LEVEL.shr [OUT]      OUT по умолчанию — opq863.bin рядом с LEVEL.shr
Формат: 'OPQ1', u32 подпись таблицы (как pvs2Sig), u32 n, u32 индексы кусков[n]."""
import struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shr7read as R, tex_gate as G

OPQ_A = 250
F_ADDITIVE = 1 << 24


def table_sig(b, npc, ptab):   # viewer/pvs2.h pvs2Sig
    h = 2166136261
    for f in (0, 1):
        for i in range(npc):
            v, = struct.unpack_from('<I', b, ptab + 80 * i + (36 if f else 32)); h = ((h ^ v) * 16777619) & 0xFFFFFFFF
    return h


def main():
    src = Path(sys.argv[1]); out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name('opq863.bin')
    bb = src.read_bytes(); b = np.frombuffer(bb, np.uint8)
    npc, = struct.unpack_from('<I', bb, 8); ptab, = struct.unpack_from('<I', bb, 76)
    recs, _, _, _ = G.walk(bb)
    texop = {}
    def tex_ok(i):
        if i not in texop: texop[i] = 0 <= i < len(recs) and int(G.level0(bb, recs[i])[..., 3].min()) >= OPQ_A
        return texop[i]
    bad, tris = {}, {}
    for far in (False, True):
        t = R.load(src, far=far)
        if not len(t['FL']): continue
        fl = t['FL'].astype(np.int64); pi = t['PI']; OFF = t['OFF'].astype(np.int64); VS = np.broadcast_to(t['VS'], OFF.shape).astype(np.int64)
        tr = ((fl & 2) != 0) & ((fl & 4) == 0) & ((fl & F_ADDITIVE) == 0)
        a = np.full(len(fl), 255)
        m16 = tr & (VS == 16)
        if m16.any(): a[m16] = np.stack([b[OFF[m16] + k * 16 + 7] for k in range(3)], 1).min(1)
        for q in np.unique(pi[tr]):
            m = (pi == q) & tr
            if not far: tris[int(q)] = int(m.sum())
            if int(a[m].min()) < OPQ_A or not tex_ok(int(t['TEX'][m][0])): bad[int(q)] = 1
    good = sorted(q for q in tris if q not in bad)
    sig = table_sig(bb, npc, ptab)
    out.write_bytes(b'OPQ1' + struct.pack('<II', sig, len(good)) + struct.pack('<%dI' % len(good), *good))
    nt = sum(tris.values()); gt = sum(tris[q] for q in good)
    print(f'{src}: полупрозрачных кусков {len(tris)} ({nt} треуг); непрозрачных по данным {len(good)} ({gt} треуг, {100 * gt / max(nt, 1):.0f}%) -> {out} (подпись {sig:08x})')


if __name__ == '__main__':
    main()
