#!/usr/bin/env python3
"""Правка 413б: перепись шейдеров машин диска (art/cars/*.p3d, чанк 0x11000): у каких машин есть материалы с флагом translucent
в заголовке шейдера, но без смешивания (BLMD 0). Экспорт car_prims ставит им флаг 2 — без правила carGlass (viewer/main.c) весь
такой кузов рисовался полупрозрачным без записи глубины. На диске Роба это одна машина: frink_v (10 из 12 материалов).
  .venv/bin/python tests/hover/glass_census.py"""
import glob, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web' / 'tools'))
from convert import Converter, GAME   # noqa: E402
from p3d import read                  # noqa: E402

res = {}
for p in sorted(glob.glob(str(GAME / 'art' / 'cars' / '*.p3d'))):
    c = Converter()
    try: c.resources(read(Path(p)))
    except Exception: continue
    t = sorted(n for n, s in c.shaders.items() if s['translucent'] and not s['blend'])
    if t: res[os.path.basename(p)[:-4]] = t
for k, v in res.items(): print(k, len(v), ' '.join(v))
raise SystemExit(0 if list(res) == ['frink_v'] else 1)
