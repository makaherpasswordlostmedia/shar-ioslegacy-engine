#!/usr/bin/env python3
"""№946, игра в эмуляторе (tests/poles946/l7_tilt.txt, предмет 332 — тяжёлый столб L7): после PROPKICK столб ложится (up < 0,3) не позже чем за LIM секунд и не успевает уехать дальше MAXM метров перед машиной.
python3 check_game.py smoke.txt [--expect fail]"""
import re, sys
a = sys.argv[1:]; exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
LIM, MAXM = 1.2, 25.
tk = None; fall = None; far = 0.
for l in open(a[0], errors='replace'):
    m = re.match(r'PROPKICK i=332 .* t=(\S+)', l)
    if m and tk is None: tk = float(m.group(1)); continue
    m = re.match(r'PROPSTAT i=332 .* moved=(\S+) up=(\S+) .* t=(\S+)', l)
    if m and tk is not None:
        mv, up, t = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if fall is None:
            far = max(far, mv)
            if up < .3: fall = t - tk
ok = fall is not None and fall <= LIM and far <= MAXM
print(f'столб 332: удар t={tk}; лёг через {fall if fall is None else round(fall, 2)} с (предел {LIM}); уехал перед машиной до падения {far:.0f} м (предел {MAXM:.0f})  ->  ' + ('годится' if ok else 'не годится'))
sys.exit(0 if ok != exp_fail else 1)
