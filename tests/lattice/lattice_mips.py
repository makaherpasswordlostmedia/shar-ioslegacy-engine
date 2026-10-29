#!/usr/bin/env python3
"""Гейт правки 904 (L1 F9-1: ворота Бернса издалека «дырявые»): считает прутья ворот на кадре с высоты 22 м (сценарий gate22.txt, flag lattice 0|1)
и сверяет правило решёток (viewer/main_levels.h latticeScan).
    python3 tests/lattice/lattice_mips.py OLD.png NEW.png smoke_new.txt
Условия: (1) в журнале нового прогона есть LATTICE для 128×128 с толщиной < 0.11 и levels=8->2; (2) число тёмно-красных прутьев на строке (медиана по 16
строкам тела ворот, рамка 165..325 × 118..142) у нового не меньше, чем у старого + 2, и не меньше 21 (старое: рваные прутья сливаются в клочки, 17..19)."""
import sys, re
import numpy as np
from PIL import Image

def runs(path):
    im = np.asarray(Image.open(path).convert('RGB')).astype(int); out = []
    for y in range(118, 142):
        row = im[y, 165:325]; dark = (row[:, 0] < 120) & (row[:, 1] < 70) & (row[:, 2] < 70)
        out.append(int((dark[1:] & ~dark[:-1]).sum()))
    return float(np.median(out[4:20]))

old, new = runs(sys.argv[1]), runs(sys.argv[2]); log = open(sys.argv[3], errors='replace').read()
ok_log = bool(re.search(r'LATTICE tex=\d+ 128x128 thick=0\.0\d+ levels=8->2', log))
print(f'прутьев на строке: старое {old:.0f}, новое {new:.0f}; LATTICE в журнале: {ok_log}')
sys.exit(0 if ok_log and new >= old + 2 and new >= 21 else 1)
