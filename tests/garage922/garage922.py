#!/usr/bin/env python3
"""№922: спавн в машине у дома (L1, L4, L7): глаз камеры не внутри геометрии (кадр не коричневый). По CAMIN сцены SP_L<n> (flag camingeom 1, caminlog):
глаз за стеной мира (eye) и ближняя плоскость в мире/земле (near, ground) = 0, и ни одного кадра CAMINF с битами 128 (видимый пол/крыша режется ближней плоскостью) или 256 (видимая стена).
Красный контроль: flag camwallupold 1 -> FAIL на L4 и L7.   python3 garage922.py smoke.txt --scene SP_L4 [--expect fail]"""
import re, sys
a = sys.argv[1:]; scene = a[a.index('--scene') + 1]; exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
sc = None; camin = None; bad = 0
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); continue
    if sc != scene: continue
    m = re.match(r'CAMIN .*? frames=(\d+) any=(\d+) eye=(\d+) near=(\d+) ground=(\d+)', l)
    if m and int(m.group(1)) > 30: camin = dict(zip(('frames', 'any', 'eye', 'near', 'ground'), map(int, m.groups())))
    m = re.match(r'CAMINF t=\S+ fl=(\d+)', l)
    if m and int(m.group(1)) & (128 | 256): bad += 1
if not camin: print(scene + ': нет строки CAMIN'); print('FAIL'); sys.exit(0 if exp_fail else 1)
ok = camin['eye'] == 0 and camin['near'] == 0 and camin['ground'] == 0 and bad == 0
print(f'{scene}: кадров {camin["frames"]}; глаз за стеной {camin["eye"]}, ближняя плоскость в мире {camin["near"]}, в земле {camin["ground"]}; кадров с режущейся видимой крышей/стеной {bad}')
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok != exp_fail else 1)
