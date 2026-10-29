#!/usr/bin/env python3
"""Разбор расхождений камеры комнаты: порт против записи PS2 (прогон ps2s_room.py или visit.tsv/walk.tsv): группы кадров с глазом > 0,6 м или
взглядом > 5°: Гомер, глаз PS2 / порта, имя камеры порта, в каких триггерах Гомер.
  python3 tests/rooms/roomcam_diff.py ПАКЕТ.bin КОМНАТА ЗАПИСЬ.tsv [trace|visit|walk] [yстарт]"""
import math, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roomcam_twins as T
pkg, room, path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]); kind = sys.argv[4] if len(sys.argv) > 4 else 'trace'
orig = T.original(path, ('trace', float(sys.argv[5]) if len(sys.argv) > 5 else -20.0) if kind == 'trace' else kind)
host = T.build(0); tsv = T.ROOT / 'build/rooms_cams/path_diff.tsv'
tsv.write_text(''.join(f'{f} {x:.3f} {z:.3f}\n' for f, x, z, _, _ in orig))
res = subprocess.run([str(host), str(pkg), room, str(tsv)], capture_output=True, text=True, check=True).stdout
port = {int(l.split('\t')[0]): l.split('\t') for l in res.splitlines()}
bad = []
for i, (f, x, z, e, d) in enumerate(orig):
    if any(math.dist(orig[j][3], orig[j - 1][3]) > .5 for j in range(max(1, i - 7), i + 1)): continue   # смена камеры у оригинала: не в счёт (как у гейта)
    p = port.get(f)
    if not p: continue
    pe = [float(v) for v in p[2:5]]; pl = [float(v) for v in p[5:8]]; pd = [pl[k] - pe[k] for k in range(3)]; n = math.sqrt(sum(v * v for v in pd)) or 1.0
    ang = math.degrees(math.acos(max(-1, min(1, sum(a * b / n for a, b in zip(pd, d))))))
    if math.dist(e, pe) > T.EYE_TOL or ang > T.ANG_TOL: bad.append((f, x, z, e, pe, p[1], ang))
print(f'{room}: кадров {len(orig)}, расхождений {len(bad)}')
g = []
for b in bad:
    if g and b[0] - g[-1][-1][0] <= 6 and b[5] == g[-1][-1][5]: g[-1].append(b)
    else: g.append([b])
for grp in g:
    a, z_ = grp[0], grp[-1]
    print(f'  кадры {a[0]}–{z_[0]} ({len(grp)}): Гомер ({a[1]:.2f},{a[2]:.2f})→({z_[1]:.2f},{z_[2]:.2f}) порт {a[5]} глаз PS2 {[round(v,1) for v in a[3]]} порт {[round(v,1) for v in a[4]]} взгляд до {max(q[6] for q in grp):.0f}°')
