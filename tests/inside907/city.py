#!/usr/bin/env python3
"""№907-город: куски ГОРОДА (owner 0) с флагом 2 (не аддитивный, не небо), у которых смешивание пустое: текстура непрозрачна и вершины с альфой >= 250.
Только чтение level.shr. python tests/inside907/city.py LEVEL.shr [--list]   (код возврата 1, если такие куски есть)"""
import sys, struct
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import census
F_NOIDX, F_V12 = 16, 32
F_FARP = 1 << 25   # viewer/main_render.h: у куска есть дальняя версия без нарезки

def city_noop(b, topq):
    """-> список (номер куска, tex, треугольников, bbox, флаги, пустое_смешивание) по всем городским кускам с флагом 2"""
    ptab, = struct.unpack_from('<I', b, 76); npc, = struct.unpack_from('<I', b, 8); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    out = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        tex, fl, nv, ni, own = r[6:11]; off, nf, ci = r[15:18]
        if own != 0 or not (fl & 2) or (fl & (4 | census.F_ADD)): continue
        opq = 0 <= tex < len(topq) and topq[tex]
        alpha_ok = None
        if opq:
            if fl & F_V12: alpha_ok = True
            elif fl & F_NOIDX:
                a = np.frombuffer(b, np.uint8, ni * 16, cells[ci][9] + off).reshape(ni, 16)[:, 7]; alpha_ok = bool(a.min() >= census.NOOP_ALPHA)
            else: alpha_ok = False   # индексный формат не читаем: считаем непустым (консервативно)
        out.append((i, tex, ni // 3, r[:6], fl, bool(opq and alpha_ok)))
    return out

def plan(b, topq):
    """правило движка (viewer/main_levels.h opq863Apply): снять флаг 2 у кусков с пустым смешиванием, кроме «листов» моря (есть дальняя версия, втрое и более дешевле ближней).
    -> (снять [(номер куска, треугольников, смещение флагов в файле)], оставить [...])"""
    ptab, = struct.unpack_from('<I', b, 76); un, keep = [], []
    for (i, tex, tr, bb, fl, ok) in city_noop(b, topq):
        if not ok: continue
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i); ni, nf = r[9], r[16]
        (keep if (nf and nf * 10 <= ni * 3 and (fl & F_FARP)) else un).append((i, tr, ptab + 80 * i + 28))
    return un, keep

if __name__ == '__main__':
    p = sys.argv[1]; b = Path(p).read_bytes(); topq = census.tex_opaque(b); L = city_noop(b, topq)
    n = [x for x in L if x[5]]
    print('%s: кусков города с флагом 2: %d, из них пустое смешивание: %d (треугольников %d); непрозрачная текстура, но вершины с альфой: %d' %
          (p.split('/')[-2] + '/' + p.split('/')[-1], len(L), len(n), sum(x[2] for x in n), sum(1 for x in L if 0 <= x[1] < len(topq) and topq[x[1]]) - len(n)))
    if '--list' in sys.argv:
        for (i, tex, tr, bb, fl, ok) in n[:60]: print('  кусок %d tex %d треуг. %d флаги %d bbox x %.0f..%.0f z %.0f..%.0f' % (i, tex, tr, fl, bb[0], bb[3], bb[2], bb[5]))
    sys.exit(1 if n else 0)
