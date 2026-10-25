#!/usr/bin/env python3
"""Куча уровня (№934): сверка с базой (сборка без правок №934, TEST59-эквивалент) по smoke.txt.
Точная цифра: строка HZLOAD level=N ... free=БАЙТ (куча сразу после загрузки ленты уровня N; в базу эта строка вставлена тем же текстом): новая ≥ база − TOL байт (по умолчанию 10240 = 0,01 МБ).
Вторая цифра, грубая (2 знака МБ): «STAT FOOT ... heapmin Y» — не хуже базы на 0,02 МБ (две округлённые цифры дают до 0,02 шума).   heap.py base_smoke new_smoke LEVEL [--tol БАЙТ] [--expect-fail]"""
import sys, re
ef = '--expect-fail' in sys.argv; tol = 10240
if '--tol' in sys.argv: tol = int(sys.argv[sys.argv.index('--tol') + 1])
pos = [a for a in sys.argv[1:] if not a.startswith('--') and a != str(tol)]; fb, fn, L = pos[0], pos[1], pos[2]
def get(f):
    t = open(f, errors='replace').read(); m = re.findall(r'HZLOAD level=%s .*? free=(\d+)' % L, t); s = re.findall(r'STAT FOOT .*?heapmin ([0-9.]+)', t)
    return (int(m[-1]) if m else None, float(s[-1]) if s else None)
b = get(fb); n = get(fn)
if None in b + n: print('нет цифр кучи: база %s, новая %s' % (b, n)); sys.exit(0 if ef else 1)
ok = n[0] >= b[0] - tol and n[1] >= b[1] - 0.02 - 1e-9
print('куча после ленты L%s: база %d, новая %d (Δ %+d Б, допуск −%d); минимум в городе %.2f → %.2f МБ  %s' % (L, b[0], n[0], n[0] - b[0], tol, b[1], n[1], 'ОК' if ok else 'ХУЖЕ'))
sys.exit(0 if (ok != ef) else 1)
