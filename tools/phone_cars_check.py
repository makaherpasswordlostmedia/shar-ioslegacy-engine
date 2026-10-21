#!/usr/bin/env python3
"""Будка (№535/№474): каждая машина галереи phonecars.txt, которую игрок может вызвать на уровне N, должна быть в msncars-lN.shr
(иначе gameMsnPhoneCar -> mcGeoFind пусто -> «приехала основная»), блок читается целиком, текстур <= MCR_TEXPER (16).
  python3 tools/phone_cars_check.py PACKAGE_DIR [УРОВНИ]    (например 3 или 1,2,3; по умолчанию все семь)
Выход 1, если есть пропуски. Себя (defaultcar текущего уровня) не проверяет: это машина игрока."""
import re, struct, sys
from pathlib import Path
pkg = Path(sys.argv[1]); bad = 0
levels = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2][0].isdigit() else range(1, 8)
for n in levels:
    d = pkg if n == 1 else pkg / f'l{n}'
    rows = [l.split() for l in (d / 'phonecars.txt').read_text().splitlines() if l.strip()]
    f = d / f'msncars-l{n}.shr'
    if not f.exists(): print(f'L{n}: нет {f.name}'); bad += 1; continue
    b = f.read_bytes(); h = struct.unpack_from('<8I', b, 0); cat = {}
    for i in range(h[3]):
        o = h[4] + i * 176; nm = b[o:o + 16].split(b'\0')[0].decode().lower(); u = struct.unpack_from('<8I', b, o + 144); cat[nm] = u
    miss, broken = [], []
    for r in rows:
        nm = r[0].lower(); own = (r[7] == 'defaultcar' and int(r[1]) >= n)   # defaultcar своего уровня — машина игрока; более поздних уровней — недоступна
        if own: continue
        u = cat.get(nm)
        if u is None: miss.append(r[0]); continue
        if u[0] + u[1] > len(b) or u[7] > 16 or u[1] == 0: broken.append(f'{r[0]}(блок {u[0]}+{u[1]}, текстур {u[7]})')
    print(f'L{n}: машин в пакете {len(cat)}, размер {len(b)/1048576:.1f} МБ; нет модели: {miss or "—"}; битые: {broken or "—"}')
    bad += len(miss) + len(broken)
sys.exit(1 if bad else 0)
