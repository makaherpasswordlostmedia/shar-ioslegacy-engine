#!/usr/bin/env python3
# №916: ряды по сценам из CTRLYAW (t, frame — кадр управления, walk — курс скорости ходьбы, camYaw, spd, pos) и CAMF (глаз). Печать: раз в 0,5 с в сцене.
import re, sys, math
w = lambda x: (x + 180) % 360 - 180
sc = None; rows = {}; eye = {}
for l in open(sys.argv[1], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); continue
    m = re.search(r'CTRLYAW t=(\S+) held=(\S+) view=(\S+) camYaw=(\S+) busy=(\d) bt=\S+ spd=(\S+) on=(\d) frame=(\S+) walk=(\S+) pos=(\S+),(\S+)', l)
    if m and sc: rows.setdefault(sc, []).append([float(m.group(1)), float(m.group(8)), float(m.group(9)), float(m.group(4)), float(m.group(3)), float(m.group(6)), int(m.group(5)), float(m.group(10)), float(m.group(11))])
want = sys.argv[2].split(',') if len(sys.argv) > 2 else list(rows)
for s in want:
    r = rows.get(s, []); print('==', s, 'кадров', len(r)); print('   t     frame  walk  dWalk  camYaw  view  spd  busy  pos')
    last = -9
    for x in r:
        if x[0] - last >= 0.5: last = x[0]; print('%6.1f %6.0f %6.0f %6.0f %7.0f %6.0f %5.1f %3d  %.1f,%.1f' % (x[0], x[1], x[2], w(x[2] - r[0][2]), x[3], x[4], x[5], x[6], x[7], x[8]))
