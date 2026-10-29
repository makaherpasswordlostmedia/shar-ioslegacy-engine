#!/usr/bin/env python3
"""№933: перепись кусков со сложением (F_ADDITIVE, 1<<24) и слоёв-наклеек со смешиванием по level.shr (только файл): город, пропы, стейтпропы, число экземпляров.
    python tests/glow933/census.py LEVEL.shr [...]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'inside907'))
import census as c
F_ADD, F_SKY, F_LAYER = 1 << 24, 4, 64
for p in [a for a in sys.argv[1:]]:
    b = Path(p).read_bytes(); props, sprops, city = c.pieces_of(b)
    ca = [x for x in city if x[1] & F_ADD]; cl = [x for x in city if (x[1] & 2) and (x[1] & (F_LAYER | 256 | 1024)) and not x[1] & F_SKY]
    pa = [x for x in props if x[1] & F_ADD]; sa = [x for x in sprops if x[1] & F_ADD]
    print('%s: город: со сложением %d кусков (текстур %d), слоёв-наклеек %d | пропы: со сложением %d кусков, экземпляров %d | стейтпропы: со сложением %d кусков, экземпляров %d' % (
        p.split('/')[-2] + '/' + p.split('/')[-1], len(ca), len(set(x[0] for x in ca)), len(cl), len(pa), sum(x[4] for x in pa), len(sa), sum(x[4] for x in sa)))
