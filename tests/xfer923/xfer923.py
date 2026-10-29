#!/usr/bin/env python3
"""№923: перенос героя/машины на 100 м и дальше (RESET CAR, респавн): самый тяжёлый кадр правила глаза камеры (CAMIN usmax, мкс) в сцене XF_b не больше LIM мс (по умолчанию 50).
Красный контроль: flag camxferold 1 -> FAIL (316 мс).   python3 xfer923.py smoke.txt [--lim 50] [--expect fail]"""
import re, sys
a = sys.argv[1:]; LIM = float(a[a.index('--lim') + 1]) if '--lim' in a else 50.
exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
sc = None; us = None
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); continue
    if sc != 'XF_b': continue
    m = re.match(r'CAMIN .*? frames=(\d+) .*? usmax=(\d+)', l)
    if m and int(m.group(1)) > 30: us = int(m.group(2))
if us is None: print('XF_b: нет строки CAMIN'); print('FAIL'); sys.exit(0 if exp_fail else 1)
ok = us / 1000. <= LIM
print(f'XF_b: самый тяжёлый кадр правила глаза {us / 1000.:.1f} мс (предел {LIM:.0f} мс)'); print('PASS' if ok else 'FAIL')
sys.exit(0 if ok != exp_fail else 1)
