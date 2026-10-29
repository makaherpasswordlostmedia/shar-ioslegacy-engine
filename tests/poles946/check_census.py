#!/usr/bin/env python3
"""№946/№968: перепись заездов (census.c, режим P) — высокие предметы (hH >= 2: столбы, фонари, деревья) после удара обязаны упасть (вертикальность < 0,3), и не быстрее и не медленнее, чем в оригинале.
PS2 (замер №968, фонарь L1, 8–12 м/с): до 72° от первого наклона 2,7–3,3 с; порт на шарнире 2,1–3,0. Окно медианы 1,5…3,3 с (прежнее №946 валило за 0,6; без №946 — стоймя дольше 1,5 с) и не больше 3 % предметов не падают за 4 с.
python3 check_census.py P_LEVEL.txt [--expect fail]"""
import re, sys
a = sys.argv[1:]; exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
ts = []
for l in open(a[0], errors='replace'):
    if not l.startswith('P\t'): continue
    f = l.rstrip('\n').split('\t'); hH = float(re.search(r'hH (\S+)', f[3]).group(1)); m = re.search(r'fall (\S+)', l)
    if hH >= 2.0 and f[-1] == 'OK' and m: ts.append(float(m.group(1)))
ts.sort(); n = len(ts); med = ts[n // 2] if n else 99.; slow = sum(1 for t in ts if t > 4.0); share = 100. * slow / n if n else 100.
ok = n >= 50 and 1.5 <= med <= 3.3 and share <= 3.
print(f'высоких сбитых {n}; медиана падения {med:.2f} с (окно 1,5…3,3); не упали за 4 с: {slow} = {share:.1f} % (предел 3 %)  ->  ' + ('годится' if ok else 'не годится'))
sys.exit(0 if ok != exp_fail else 1)
