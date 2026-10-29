#!/usr/bin/env python3
# №973: разбор строк SHADOW973 из smoke.txt. check.py drive FILE [СЦЕНА] — езда: кадров всего, кадров с вершиной тени ниже опоры (sunk0), худший зазор; check.py shape FILE — несимметрия контура.
# Код 0 = «тень лежит на опоре» (drive: sunk0 не больше 1 % кадров) / «контур симметричен» (shape: до 0,05 м).
import re, sys
mode, f = sys.argv[1], sys.argv[2]; scene = sys.argv[3] if len(sys.argv) > 3 else None
rows = []
for l in open(f, encoding='utf-8', errors='replace'):
    if not l.startswith('SHADOW973'): continue
    d = dict(re.findall(r'(\w+)=(\S+)', l))
    if scene and d.get('sc') != scene: continue
    if int(d.get('n', 0)) == 0: continue
    rows.append(d)
if not rows: print('нет строк SHADOW973'); sys.exit(2)
if mode == 'drive':
    n = sum(int(r['n']) for r in rows); s0 = sum(int(r['sunk0']) for r in rows); s5 = sum(int(r['sunk5']) for r in rows)
    worst = min(float(r['minclr']) for r in rows); high = max(float(r['maxclr']) for r in rows)
    print(f'кадров {n}, вершина тени ниже опоры в {s0} ({100.0*s0/n:.2f} %), ниже опоры + 5 см в {s5} ({100.0*s5/n:.2f} %), худший зазор {worst:.2f} м, наибольший над опорой {high:.2f} м')
    sys.exit(0 if s0 <= 0.01 * n else 1)
else:
    a = max(float(r['asym']) for r in rows)
    print(f'несимметрия контура тени до {a:.3f} м')
    sys.exit(0 if a <= 0.05 else 1)
