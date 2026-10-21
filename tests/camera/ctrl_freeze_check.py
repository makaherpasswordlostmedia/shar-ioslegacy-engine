#!/usr/bin/env python3
"""№704: гейт «управление не связано с облётом камеры»: стик «вперёд» нажат, когда камера уже крутится; курс ходьбы (первые 0,5 с) отличается от вида камеры ДО облёта не больше LIM°.
Сцены EXB_<new|old>_<задержка> (tests/smoke_scenes/booth_hold.txt). Красный контроль: *_old (flag ctrlfreezeold 1) должен дать FAIL хотя бы в одной задержке; PASS — все *_new в пределе.
python3 tests/camera/ctrl_freeze_check.py smoke.txt [--lim 25]"""
import re, math, sys
a = sys.argv[1:]; LIM = float(a[a.index('--lim') + 1]) if '--lim' in a else 25.
w = lambda x: (x + 180) % 360 - 180
sc = None; prev = None; pre = None; t0 = None; res = {}
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); prev = None; pre = None; t0 = None; continue
    if not sc or not sc.startswith('EXB'): continue
    m = re.match(r'CAMF t=(\S+) st=(\d+) .*? eye=(\S+) look=(\S+) homer=(\S+) ', l)
    if not m: continue
    t = float(m.group(1)); h = [float(x) for x in m.group(5).split(',')]; e = [float(x) for x in m.group(3).split(',')]; lk = [float(x) for x in m.group(4).split(',')]
    cam = math.degrees(math.atan2(lk[0] - e[0], lk[2] - e[2]))
    if t0 is None: t0 = t
    if t < t0 + 1.9: pre = cam   # вид до облёта (облёт стартует через 2 с после начала сцены)
    elif prev and pre is not None:
        dx, dz = h[0] - prev[0], h[2] - prev[1]
        if math.hypot(dx, dz) > 0.03:
            r = res.setdefault(sc, [t, 0.])
            if t - r[0] < 0.5: r[1] = max(r[1], abs(w(math.degrees(math.atan2(dx, dz)) - pre)))
    prev = (h[0], h[2])
ok = True; olds = []
for s, (t, d) in sorted(res.items()):
    print(f"{s}: курс ходьбы отличается от вида до облёта на {d:.0f}° (предел {LIM})")
    if s.startswith('EXB_new'): ok = ok and d <= LIM
    else: olds.append(d)
print("красный контроль (старое) макс", f"{max(olds):.0f}°" if olds else "нет данных", "-> " + ("FAIL как и должно" if olds and max(olds) > LIM else "НЕ КРАСНЕЕТ"))
print("PASS" if ok and res else "FAIL"); sys.exit(0 if ok and res else 1)
