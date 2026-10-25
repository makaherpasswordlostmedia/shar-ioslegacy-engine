#!/usr/bin/env python3
"""Гейт правки 897 (L1 J3-2: четыре тонких вертикальных линии «тросы»): каждая линия контура мультика (toonlines.shr, TLN2) обязана
опираться концами на вершины видимого города level.shr. Линии мешей, которые в город не идут (стейтпропы, анимированные объекты, типы пропов:
башня ветряной мельницы windmilShape0 в осях объекта), этому не отвечают — это «призраки».
    python3 tests/toon/ghost_lines.py level.shr toonlines.shr [допуск_м=0.3]
Выход 0 — призраков нет, 1 — есть (печатает число и клетки 20 м). Красный контроль: toonlines.shr, собранный SHR_TOON_ALL_OLD=1 (старое правило экспорта) —
L1: 235 призраков (мельница (160, −480) ×72, начало координат (0, 0) ×124 + соседи 16, (140, −300) ×20, (160, −300) ×3); зелёный — новое правило: 0.
Только чтение файлов, на Маке."""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import numpy as np
import shr7read as s

def main():
    level, tl = sys.argv[1], sys.argv[2]; tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
    V = s.load(level)['P'].reshape(-1, 3); G = 0.5
    c = np.floor(V / G).astype(np.int64); k = (c[:, 0] * 73856093) ^ (c[:, 1] * 19349663) ^ (c[:, 2] * 83492791)
    o = np.argsort(k); k, V = k[o], V[o]
    def has(p):
        c0 = np.floor(p / G).astype(np.int64)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for l in (-1, 0, 1):
                    kk = ((c0[0] + i) * 73856093) ^ ((c0[1] + j) * 19349663) ^ ((c0[2] + l) * 83492791)
                    a, b = np.searchsorted(k, kk, 'left'), np.searchsorted(k, kk, 'right')
                    if b > a and (np.abs(V[a:b] - p).max(1) < tol).any(): return True
        return False
    b = Path(tl).read_bytes(); nc, nl = struct.unpack_from('<II', b, 4)
    cells = [struct.unpack_from('<hhII', b, 12 + 12 * i) for i in range(nc)]; base = 12 + 12 * nc; bad = []
    for cx, cz, f, n in cells:
        for kx in range(f, f + n):
            p = np.array(struct.unpack_from('<6h', b, base + 12 * kx), float) / 100.0; p[[0, 3]] += cx * 64; p[[2, 5]] += cz * 64
            if not (has(p[:3]) and has(p[3:])): bad.append(p)
    cl = {}
    for p in bad: kk = (round((p[0] + p[3]) / 40) * 20, round((p[2] + p[5]) / 40) * 20); cl[kk] = cl.get(kk, 0) + 1
    print(f'линий {nl}, без вершины города на концах: {len(bad)}', dict(sorted(cl.items())))
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
