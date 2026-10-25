#!/usr/bin/env python3
"""№947б (бывш. №920): курс ходьбы держится, пока стик не менялся игроком, и когда камеру перескочила сама игра (перескок у стены; CAMFLIP). По CTRLYAW/CAMF (flag camlog) сцен tests/ctrl916/ctrl920.txt:
  TW_down: стик вниз 6 с, идём на камеру, она разворачивается за спину (камера повернулась больше 60°);
  WJ_cont: прыжки вдоль стены с зажатым стиком, камера отходит от стены (больше 60°), прыжков не меньше 3;
  WJ_drop: то же, стик на 0,1 с уходит в ноль каждую секунду.
В каждой сцене курс (скорость Гомера в мире, пока он идёт быстрее 1 м/с) не отклоняется от первого больше LIM° (по умолчанию 10), в том числе в прыжке и после приземления.
В WJ_drop стик на 0,1 с уходит в ноль уже после перескока: без заморозки курса (flag flipbusyold 1) ход брался от ушедшего вида. Красный контроль: flag flipbusyold 1 -> WJ_drop FAIL:  python3 ctrl920.py smoke.txt --expect fail
"""
import re, sys
a = sys.argv[1:]; LIM = float(a[a.index('--lim') + 1]) if '--lim' in a else 10.
exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
w = lambda x: (x + 180) % 360 - 180
sc = None; R = {}; Y = {}
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', l)
    if m: sc = m.group(1); continue
    m = re.search(r'CTRLYAW t=(\S+) held=\S+ view=\S+ camYaw=(\S+) busy=\d bt=\S+ spd=(\S+) on=\d frame=(\S+) walk=(\S+) pos=', l)
    if m and sc: R.setdefault(sc, []).append([float(x) for x in m.groups()])   # t, camYaw, spd, frame, walk
    m = re.search(r'CAMF t=(\S+) .*? homer=(\S+?),(\S+?),(\S+?) ', l)
    if m and sc: Y.setdefault(sc, []).append((float(m.group(1)), float(m.group(3))))
def jumps(ys):
    """число прыжков: подъём Гомера не меньше 0,8 м над самой низкой точкой за последние 2 с"""
    n = 0; up = False
    for i, (t, y) in enumerate(ys):
        lo = min(v for tt, v in ys[max(0, i - 60):i + 1]) if i else y
        if y - lo > .8 and not up: n += 1; up = True
        elif y - lo < .3: up = False
    return n
ok = True
for name, need_jumps in (('TW_down', 0), ('WJ_cont', 3), ('WJ_drop', 3)):
    rows = R.get(name, []); mv = [r for r in rows if r[2] > 1.0]
    if not mv: print(name + ': нет ходьбы'); ok = False; continue
    c0 = mv[0][4]; dev = max(abs(w(r[4] - c0)) for r in mv)
    cam = max(abs(w(r[1] - mv[0][1])) for r in mv); nj = jumps(Y.get(name, []))
    good = dev <= LIM and cam > 60. and nj >= need_jumps
    print(f'{name}: курс {c0:.0f}°, наибольшее отклонение {dev:.0f}° (предел {LIM:.0f}°); камера повернулась на {cam:.0f}°; прыжков {nj}' + ('' if good else '  <-- не годится'))
    ok = ok and good
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok != exp_fail else 1)
