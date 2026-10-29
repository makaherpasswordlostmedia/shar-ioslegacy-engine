"""Правка Роба 226 («знаки STOP задом наперёд, везде»): текстуры, которые на диске лежат PNG (вывески уровня 1: StopSign, elemsign,
chruchSign, powerplantsigns, ComCentreSign), попадают в пакет уровня перевёрнутыми по вертикали (строки PNG сверху вниз, у Pure3D
v снизу вверх). Проверка тем же загрузчиком, что пишет level.shr (texq.load_tex, как в psp_export): уровень 0 записанной
текстуры ближе к перевёрнутому исходнику, чем к прямому, — у каждой PNG-текстуры уровня 1. Картинки в формате PS2 (P3DI) —
не переворачиваются. SHR_PNG_FLIP=0 — прежнее (красный: обязан упасть).  python3 tests/tex226/check.py -> 0 = PASS"""
import os, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.argv = sys.argv[:1]
import psp_export as pe
import texq
from convert import Converter

conv = Converter()
for zone in ('l1_terra', 'l1z3', 'l1r2', 'l1r6'):
    conv.resources(pe.read(pe.GAME / 'art' / f'{zone}.p3d'))
urls = sorted(u for u in pe.PNG_SRC)
if not urls: print('FAIL: PNG-текстур не найдено'); sys.exit(1)
bad = 0; checked = 0
for url in urls[:12]:
    cache, blob = {}, []
    i = pe.load_tex(url, cache, blob)
    if i < 0 or not blob: continue
    lv = texq.decode(blob[i])[0]          # уровень 0, RGBA
    src = Image.open(pe.ASSETS / url).convert('RGB').resize((lv.shape[1], lv.shape[0]), Image.LANCZOS)
    got = lv[..., :3].astype(float); a = np.asarray(src, float); f = a[::-1]
    d_flip, d_same = np.abs(got - f).mean(), np.abs(got - a).mean()
    ok = d_flip < d_same; checked += 1; bad += not ok
    print(f'{url}: к перевёрнутому {d_flip:.1f}, к прямому {d_same:.1f} -> {"перевёрнута" if ok else "НЕ перевёрнута"}')
print(f'RESULT {"PASS" if checked and not bad else "FAIL"} ({checked} текстур, не перевёрнуто {bad})')
sys.exit(0 if checked and not bad else 1)
