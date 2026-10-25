#!/usr/bin/env python3
"""Сценарий гейта №934 (HOR2): глаз идёт шагом 3 м через границу двух клеток ленты на самых крутых перепадах уровня, сперва мировая лента («flag hzworld 1»), затем прежняя («flag hzworld 0»).
В каждом положении «flag hztrace 2» пишет в smoke.txt кромку нарисованной ленты (строки HZE). Пары берёт tools/hz934_jump.py --old --emit K по horizon.shr уровня (худшие по прежней ленте).
  scn.py УРОВЕНЬ horizon.shr [K=2] [ШАГ_м=3] > scenario.txt"""
import sys, subprocess, math
from pathlib import Path
L = int(sys.argv[1]); hz = sys.argv[2]; K = int(sys.argv[3]) if len(sys.argv) > 3 else 2; STEP = float(sys.argv[4]) if len(sys.argv) > 4 else 3.
tool = Path(__file__).resolve().parents[2] / 'tools/hz934_jump.py'
out = subprocess.run([sys.executable, str(tool), hz, '--old', '--emit', str(K), '--lim', '999'], capture_output=True, text=True).stdout
pairs = [tuple(float(v) for v in ln.split()[1:7]) for ln in out.splitlines() if ln.startswith('PAIR ')]
if not pairs: sys.exit('нет пар с перепадом')
print('wait 12\nscene LOAD\nflag golevel %d\nwait 40\nflag cfgdefaults 1\nscene FOOT\nwait 6\nflag stop' % L)
print('flag hztrace 2')
for world in (1, 0):
    print('flag hzworld %d\nwait 1' % world)
    for k, (x1, z1, e1, x2, z2, e2) in enumerate(pairs):
        n = math.hypot(x2 - x1, z2 - z1)
        print('scene HZP%d_%d\nfoot %.1f %.1f 0.1\nwaitload 25\nwait 2' % (world, k, x1, z1))
        s = n / 2 - 15
        while s <= n / 2 + 15 + 1e-6:
            f = s / n; x = x1 + (x2 - x1) * f; z = z1 + (z2 - z1) * f; y = e1 + (e2 - e1) * f
            print('cam %.2f %.2f %.2f 0.0 0.0 1.0\nwait 0.5' % (x, y, z))
            if abs(s - n / 2) < STEP / 2: print('shot hz%d_p%d' % (world, k))
            s += STEP
        print('wait 1')
print('flag hzworld 1\nend')
