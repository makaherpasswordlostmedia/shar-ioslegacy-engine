#!/usr/bin/env python3
"""№947/№947б: разворот бегом. По CTRLYAW (flag camlog) сцен tests/walk947/walk947.txt:
  W_thru, W_arc, W_camrev: стик резко назад (через центр / дугой / после поворота камеры игроком) — Гомер бежит К камере (вид на момент разворота + 180°), допуск 35°;
  W_twice:   вперёд, назад (камера разворачивается за спину), снова вперёд — Гомер бежит ОТ камеры (по экрану вперёд), а не на неё;
  W_camhold: камеру повернул игрок, стик не трогали — курс в мире держится (допуск 20°);
  W_jit:     дрожь стика и поворот камеры игроком — курс держится (допуск 25°).
Красный контроль: прогон с flag ctrl947old 1 (правило №916/№920: кадр управления держится, пока стик не отпущен) — FAIL:  python3 walk947.py smoke.txt --expect fail
"""
import re, sys, statistics
a = sys.argv[1:]; exp_fail = '--expect' in a and a[a.index('--expect') + 1] == 'fail'
w = lambda x: (x + 180) % 360 - 180
sc = None; S0 = {}; R = {}
for l in open(a[0], errors='replace'):
    m = re.match(r'SCENE (\S+) (\S+)', l)
    if m: sc = m.group(1); S0[sc] = float(m.group(2)); continue
    m = re.search(r'CTRLYAW t=(\S+) held=\S+ view=(\S+) camYaw=\S+ busy=\d bt=\S+ spd=(\S+) on=\d frame=\S+ walk=(\S+) pos=', l)
    if m and sc: R.setdefault(sc, []).append([float(x) for x in m.groups()])   # t, view, spd, walk
def med(rows, t0, t1, col):
    v = [r[col] for r in rows if t0 <= r[0] <= t1 and r[2] > 3.5]
    return None if not v else statistics.median(v)
def walk_end(rows):
    ws = [r for r in rows if r[2] > 3.5]
    return None if not ws else med(rows, ws[-1][0] - .5, ws[-1][0], 3)
ok = True
def rep(name, good, txt):
    global ok; print(f'{name}: {txt}' + ('' if good else '  <-- не годится')); ok = ok and good
for name, back_at, off in (('W_thru', None, 180.), ('W_arc', None, 180.), ('W_camrev', 5.4, 180.), ('W_twice', 8.5, 0.)):
    rows = R.get(name, []); ws = [r for r in rows if r[2] > 3.5]
    if not ws: rep(name, False, 'нет ходьбы'); continue
    t1 = ws[0][0]; w0 = med(rows, t1 + .5, t1 + 1.5, 3); we = walk_end(rows)
    if back_at is None: exp = w(w0 + 180.); why = f'начальный курс {w0:.0f}°'
    else:
        vt = min(rows, key=lambda r: abs(r[0] - (S0[name] + back_at))); exp = w(vt[1] + off); why = f'вид на момент разворота {vt[1]:.0f}°'
    d = abs(w(we - exp)) if we is not None else 999.
    rep(name, d <= 35., f'{why}; ход в конце {we:.0f}°, ожидается {exp:.0f}° ({'на камеру' if off else 'от камеры'}); расхождение {d:.0f}° (предел 35°)')
for name, lim in (('W_camhold', 20.), ('W_jit', 25.)):
    rows = R.get(name, []); ws = [r for r in rows if r[2] > 3.5]
    if not ws: rep(name, False, 'нет ходьбы'); continue
    t1 = ws[0][0]; w0 = med(rows, t1 + .5, t1 + 1.2, 3); we = walk_end(rows); d = abs(w(we - w0))
    rep(name, d <= lim, f'курс {w0:.0f}° -> {we:.0f}°: отклонение {d:.0f}° (предел {lim:.0f}°)')
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok != exp_fail else 1)
