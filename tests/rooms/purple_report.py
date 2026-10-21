#!/usr/bin/env python3
"""Пурпур (дыры в стенах) в кадрах ходячей камеры комнат (16.10, Камера): по прогону tests/rooms/purple_grid_lN.txt с закрашенным фоном комнат.
Кадр «в счёт» — ходячая камера (rc=0 в последней строке CAMF перед SHOT); камера авторская (rc=1) считается отдельно. Пурпур — пиксели 0xFFFF00FF (допуск 24 на канал).
  .venv/bin/python tests/rooms/purple_report.py N build/smoke/<время>   -> таблица по комнатам и худшие места (кадр, Гомер, курс)"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
THR = 40
n = int(sys.argv[1]); D = Path(sys.argv[2]); rows = (D / 'smoke.txt').read_text(errors='replace').splitlines()
rc = None; homer = None; frames = []; cells = set(); rc0_in_room = rc1_in_room = 0
for l in rows:
    m = re.match(r'CAMF .* homer=(\S+) .* rc=(\d)', l)
    if m:
        homer, rc = m.group(1), int(m.group(2)); hp = [float(x) for x in homer.split(',')]
        if hp[1] < -10:   # внутри комнаты (комнаты глубоко под городом)
            cells.add((round(hp[0]), round(hp[2]))); rc0_in_room += rc == 0; rc1_in_room += rc == 1
        continue
    m = re.match(r'SHOT (\S+)', l)
    if m: frames.append((m.group(1), rc, homer))
res = {}
for name, rcv, hm in frames:
    f = D / f'{name}.png'
    if not f.exists(): continue
    a = np.asarray(Image.open(f).convert('RGB')).astype(int)
    pur = int(((abs(a[:, :, 0] - 255) < 24) & (a[:, :, 1] < 24) & (abs(a[:, :, 2] - 255) < 24)).sum())
    room = name.split('_')[0]; res.setdefault(room, []).append((name, rcv, hm, pur))
print(f'L{n}: порог {THR} пикс. пурпура на кадр 480x272')
tot = bad = 0
for room, L in res.items():
    walk = [x for x in L if x[1] == 0]; auth = [x for x in L if x[1] == 1]; unk = [x for x in L if x[1] is None]
    bw = [x for x in walk if x[3] > THR]; ba = [x for x in auth if x[3] > THR]
    tot += len(walk); bad += len(bw)
    print(f'  {room:7s} кадров {len(L):3d}: ходячая {len(walk):3d}, с пурпуром > {THR}: {len(bw):3d} ({len(bw) / max(1, len(walk)):.0%}); авторская {len(auth):3d}, с пурпуром: {len(ba)}; rc неизвестен {len(unk)}')
    for x in sorted(bw, key=lambda x: -x[3])[:5]: print(f'      худший {x[0]} пикс. {x[3]} Гомер {x[2]}')
print(f'итог L{n}: ходячих кадров в снимках {tot}, с пурпуром {bad} ({bad / max(1, tot):.0%}); покрытие маршрутов: клеток 1 м посещено {len(cells)}; кадров игры в комнатах: авторская камера {rc1_in_room}, ходячая {rc0_in_room}')
