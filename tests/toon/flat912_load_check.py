#!/usr/bin/env python3
"""Гейт №912 п.А: заливка не нагружает кадры игры после загрузки уровня (разбор журнала безголового прогона).
  flat912_load_check.py ПАПКА_ПРОГОНА [--min-levels N]
Проверки (по строкам до END):
  1) ph0 (начало кадра) в каждой секундной строке PHSEC (≥ 10 кадров) после первого FIRSTFRAME ≤ 0,3 мс; одиночная пересборка заливки на уровень ≤ 6 мс эмулятора (ТУР TEST57: ≈ 5 мс 16–25 с после каждой загрузки);
  2) нет фонового задания тона (TONEJOB start) после FIRSTFRAME: его запускал опрос flatPoll по текстурам трафика;
  3) нет кадра SLOWFRAME > 60 мс после первого FIRSTFRAME (ТУР: 300–400 мс одним кадром с FLAT);
  4) дамп FDIAG/FLATX/FLATT выключен по умолчанию (0 строк);
  5) цвет после смены уровня (А2): кадр через 32 с после golevel (col_*_a) против кадра после «flag flatdbg 0» (col_*_b, полная пересборка заливки) — отличие вне движущегося (маска b против c, поле 40 пикс.) < 0,5 % пикселей кадра;
     без пересборки после загрузки уровня (патч А): L5 ≈ 22 тыс. пикселей (дорога красная, тротуар серый)
  6) сценарий прошёл ≥ N смен уровня (FIRSTFRAME) и дошёл до END.
Выход 0 — PASS, 1 — FAIL."""
import re, sys
from pathlib import Path
d = Path(sys.argv[1]); minlv = 2
if '--min-levels' in sys.argv: minlv = int(sys.argv[sys.argv.index('--min-levels') + 1])
L = (d / 'smoke.txt').read_text(errors='replace').splitlines()
end = next((i for i, l in enumerate(L) if l.strip() == 'END'), None)
fails = []
if end is None: fails.append('нет строки END (сценарий не дошёл)'); end = len(L)
Lc = L[:end]
ff = [i for i, l in enumerate(Lc) if l.startswith('FIRSTFRAME')]
if len(ff) < minlv: fails.append(f'смен уровня {len(ff)} < {minlv}')
start = ff[0] if ff else len(Lc)
ph0 = [(float(re.search(r't=([\d.]+)', l).group(1)), float(re.search(r'ph0=([\d.]+)', l).group(1))) for l in Lc[start:] if l.startswith('PHSEC') and int(re.search(r' n=(\d+)', l).group(1)) >= 10]   # строки короче 10 кадров (первая секунда после смены уровня) — одиночная пересборка заливки (проверка 5 ниже)
mx = max((p for _, p in ph0), default=0.); bad = [(t, p) for t, p in ph0 if p > 0.3]
print(f'ph0 после FIRSTFRAME: строк {len(ph0)}, максимум {mx:.2f} мс, больше 0,3 мс: {len(bad)}')
if bad: fails.append(f'ph0 > 0,3 мс в {len(bad)} строках (первая t={bad[0][0]} ph0={bad[0][1]})')
rb = [sum(int(x) for x in re.findall(r'(?:tint|marks|lists)_us=(\d+)', l)) for l in Lc if l.startswith('FLATREBUILD')]
print(f'пересборок заливки после смены уровня: {len(rb)}, самая долгая {max(rb) if rb else 0} мкс (допуск 6000 мкс эмулятора)')
if rb and max(rb) > 6000: fails.append(f'пересборка заливки {max(rb)} мкс > 6000')
tj = [l for l in Lc[start:] if l.startswith('TONEJOB start')]
print(f'TONEJOB start после FIRSTFRAME: {len(tj)}')
if tj: fails.append(f'фоновое задание тона запущено {len(tj)} раз после загрузки')
slow = [(float(re.search(r'work=([\d.]+)', l).group(1)), l[:80]) for l in Lc[start:] if l.startswith('SLOWFRAME') or 'SLOWFRAME' in l]
slow = [(w, s) for w, s in slow if w > 60.]
print(f'кадров > 60 мс после FIRSTFRAME: {len(slow)}' + (f' (самый длинный {max(w for w, _ in slow):.0f} мс)' if slow else ''))
if slow: fails.append(f'кадров > 60 мс: {len(slow)}, максимум {max(w for w, _ in slow):.0f} мс')
dump = sum(1 for l in L if l.startswith(('FDIAG', 'FLATX', 'FLATT')))
print(f'строк дампа FDIAG/FLATX/FLATT: {dump}')
if dump: fails.append(f'дамп включён по умолчанию: {dump} строк')
print(f'смен уровня: {len(ff)}')
try:
    from PIL import Image
    import numpy as np
    def _L(p): return np.asarray(Image.open(p).convert('RGB')).astype(int)
    def _d(a, b): return np.abs(a - b).sum(2) > 30
    def _dil(m, r):
        o = m.copy()
        for ax in (0, 1):
            t = o.copy()
            for s in range(1, r + 1): t |= np.roll(o, s, ax) | np.roll(o, -s, ax)
            o = t
        return o
    for lv in ('l4', 'l5'):
        pa, pb, pc = (d / f'col_{lv}_{k}.png' for k in 'abc')
        if not (pa.exists() and pb.exists() and pc.exists()): fails.append(f'нет снимков col_{lv}_a/b/c'); continue
        a, b, c = _L(pa), _L(pb), _L(pc); ab = _d(a, b); bad_ = int((ab & ~_dil(_d(b, c), 40)).sum()); lim = int(0.005 * ab.size)
        print(f'цвет {lv}: после смены уровня против пересборки: {bad_} пикселей из {ab.size} (допуск {lim}); всего различий {int(ab.sum())}')
        if bad_ > lim: fails.append(f'цвет {lv}: {bad_} пикселей вне подвижного (допуск {lim})')
except ImportError: fails.append('нет PIL/numpy для проверки цвета')
for f in fails: print('FAIL', f)
print('PASS' if not fails else 'FAIL'); sys.exit(1 if fails else 0)
