#!/usr/bin/env python3
"""Гейт TEST19 J9-5: после последней CAMF сцены глаз позади машины (по курсу). python3 camj95.py smoke.txt  [--red: ждём провал]"""
import re, sys, math
red = '--red' in sys.argv; f = [a for a in sys.argv[1:] if not a.startswith('--')][0]
last = None
for l in open(f, errors='replace'):
    m = re.match(r'CAMF t=\S+ st=\d+ fov=\S+ eye=([-\d.]+),([-\d.]+),([-\d.]+) look=\S+ homer=\S+ car=([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)', l)
    if m: last = [float(x) for x in m.groups()]
ex, ey, ez, cx, cy, cz, h = last
back = -((ex - cx) * math.sin(h) + (ez - cz) * math.cos(h))   # +: глаз позади машины
print(f'глаз позади машины на {back:.2f} м (ждём > 5)')
ok = back > 5.0
print('PASS' if ok != red else 'FAIL'); sys.exit(0 if ok != red else 1)
