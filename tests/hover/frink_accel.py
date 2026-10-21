#!/usr/bin/env python3
"""Гейт 413б «прозрачная при разгоне»: строки CARGLASS (кадры, треугольники своей машины, tqown — её куски в очереди
полупрозрачного за окно, flips — смены порядка этих кусков после сортировки). Причина по замеру: прежний путь отправлял все 12
кусков frink_v в очередь без записи глубины; на ходу расстояния кусков до глаза меняются, сортировка переставляет их — какие
куски закрывают остальные, меняется от кадра к кадру (машина «просвечивает»). Критерий для окон стоя и на разгоне:
полупрозрачных треугольников за кадр — только прозрачное в данных (60), смен порядка — 0. Прежний путь на разгоне обязан упасть.
  frink_accel.py RUN_DIR"""
import re, sys
from pathlib import Path
rows = [dict((k, float(v)) for k, v in re.findall(r'(\w+)=(-?[\d.]+)', l)) for l in
        (Path(sys.argv[1]) / 'smoke.txt').read_text(errors='replace').splitlines() if l.startswith('CARGLASS ')]
if len(rows) != 6: print(f'FAIL строк CARGLASS {len(rows)} из 6'); sys.exit(1)
win = {'стоя': rows[1], 'разгон': rows[2], 'прежнее стоя': rows[4], 'прежнее разгон': rows[5]}
ok = lambda r: abs(r['blend'] / r['frames'] - 60) <= .5 and r['flips'] == 0
for k, r in win.items():
    print(f"  {k}: кадров {r['frames']:.0f}, полупрозрачных за кадр {r['blend'] / r['frames']:.0f}, кусков в очереди за кадр "
          f"{r['tqown'] / r['frames']:.1f}, смен порядка {r['flips']:.0f}")
bad = [k for k in ('стоя', 'разгон') if not ok(win[k])]
if bad: print('FAIL', ', '.join(bad)); sys.exit(1)
if ok(win['прежнее разгон']): print('FAIL красный (прежнее на разгоне) прошёл'); sys.exit(1)
print('PASS: на разгоне куски frink_v не переставляются; прежний путь пойман'); sys.exit(0)
