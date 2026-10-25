#!/usr/bin/env python3
"""№954: какие текстуры кусков неба движок превращает в градиент вершин (правило viewer/main_camera.h sky954Build): непрозрачная, точек дальше 16 от медианы строки
не больше 5 %, дальше 40 — не больше 0,5 %. Считает на Маке по level.shr набора. Выход: по уровню — превращаемые куски (ожидание для строки SKY954 conv=) и оставленные.
  rows.py SET [--loose]   --loose — красный контроль: порог 100 % (превращает всё, облака тоже); последняя строка PASS/FAIL
Проверки: L6 превращено 22 куска; текстуры с рисунком (облака, горы: L1 85–88, L2 94–97, L4 93–98, L5 101–105, L7 95–98) остаются текстурой; L2 93, L3 128/131, L5 99/100 — градиенты."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import shr7read as s, tex_gate as G, tex_sheet as S

def grad(rgba, loose):
    if rgba[..., 3].min() < 250: return False
    c = rgba[..., :3].astype(int); dev = np.abs(c - np.median(c, axis=1, keepdims=True)).max(-1)
    n = dev.size
    return loose or ((dev > 16).sum() * 20 <= n and (dev > 40).sum() * 200 <= n)

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; loose = '--loose' in sys.argv
    SET = a[0]; conv = {}; keep = {}
    for L in range(1, 8):
        p = SET + '/' + ('level.shr' if L == 1 else 'l%d/level.shr' % L); b = Path(p).read_bytes(); d = s.load(p, owner=2); recs, *_ = G.walk(b)
        conv[L] = []; keep[L] = []
        for t in sorted(set(int(x) for x in d['TEX'] if x >= 0)):
            rgba, _ = S.level(b, recs[t], 0); npc = len(set(d['PI'][d['TEX'] == t].tolist()))
            (conv if grad(rgba, loose) else keep)[L].append((t, npc))
        print('L%d превращается %s (кусков %d) · остаётся %s' % (L, [t for t, _ in conv[L]], sum(n for _, n in conv[L]), [t for t, _ in keep[L]]))
    ok = sum(n for _, n in conv[6]) == 22
    must_keep = {1: (85, 86, 87, 88), 2: (94, 95, 96, 97), 4: (93, 94, 95, 96, 97, 98), 5: (101, 104, 105), 7: (95, 96, 97, 98)}
    must_conv = {2: (93,), 3: (128, 131), 5: (99, 100), 6: (127, 128, 129)}
    for L, ts in must_keep.items(): ok &= all(t in [k for k, _ in keep[L]] for t in ts)
    for L, ts in must_conv.items(): ok &= all(t in [k for k, _ in conv[L]] for t in ts)
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1

sys.exit(main())
