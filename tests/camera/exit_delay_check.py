#!/usr/bin/env python3
"""№678: гейт «вышел из машины, подождал (камера разворачивается), потом стик вперёд»: ход Гомера в первые 0,6 с ходьбы не отклоняется
от курса машины больше LIM° (по PS2 камера после выхода держит курс машины, ≤15° за 1,6 с). Сцена tests/smoke_scenes/exitcar_delay.txt (EXW_*).
Красный контроль: сборка с flag homerflipstandold 1 (перескок камеры у стоящего Гомера) даёт FAIL.   python3 tests/camera/exit_delay_check.py smoke.txt [--lim 25]"""
import re, math, sys
a = sys.argv[1:]; LIM = float(a[a.index('--lim') + 1]) if '--lim' in a else 25.
w = lambda x: (x + 180) % 360 - 180
sc = None; prev = None; res = {}
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); prev = None; continue
    if not sc or not sc.startswith('EXW'): continue
    m = re.match(r'CAMF t=(\S+) st=(\d+) .*? homer=(\S+) car=\S+,\S+,\S+,(\S+) ', l)
    if not m: continue
    t = float(m.group(1)); h = [float(x) for x in m.group(3).split(',')]; car = math.degrees(float(m.group(4)))
    if prev and int(m.group(2)) == 0:
        dx, dz = h[0] - prev[0], h[2] - prev[1]
        if math.hypot(dx, dz) > 0.03:
            r = res.setdefault(sc, [t, 0.])
            if t - r[0] < 0.6: r[1] = max(r[1], abs(w(math.degrees(math.atan2(dx, dz)) - car)))
    prev = (h[0], h[2])
ok = len(res) >= 4
for s, (t, d) in sorted(res.items()):
    print(f"{s}: отклонение хода от курса машины {d:.0f}° (предел {LIM})"); ok = ok and d <= LIM
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
