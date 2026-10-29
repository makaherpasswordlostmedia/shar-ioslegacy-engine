#!/usr/bin/env python3
# №976: гейты точки цели. check976.py host NEW.txt OLD.txt | frames NONE OLD NEW | ring NEW_SMOKE OLD_SMOKE
#   host    ход столба звёзд (host.c №976): яркость вдвое меньше, ускорение и скачки малы, кольцо ровнее (прогиб)
#   frames  кадры входа e00..e07 (камера на кружок): масса звёзд new/old 0,15..0,6 относительно сборки none (звёзды погашены), серия живая
#   ring    строка SPHERE976 журнала смоука: у нового кольца ≥ 40 сторон, у прежнего 18
import sys, os, re
from PIL import Image
import numpy as np
def load(d, n): return np.asarray(Image.open(os.path.join(d, n + '.png')).convert('RGB')).astype(int)
def host(nf, of):
    def rd(f):
        for l in open(f):
            m = re.match(r'HOST976 model=\S+ peak_alpha=([\d.]+) vmax=([\d.]+) accel_max=([\d.]+) alpha_step=([\d.]+) star_step=([\d.]+) radius_step=([\d.]+) sag=([\d.]+)', l)
            if m: return [float(x) for x in m.groups()]
    n, o = rd(nf), rd(of); bad = 0
    if not n or not o: print('нет строки HOST976'); return 1
    print('яркость звёзд (пик): new %.2f old %.2f; ускорение фронта: new %.0f old %.0f; шаг яркости звезды за кадр: new %.2f old %.2f; шаг яркости столба: new %.3f old %.3f; прогиб кольца: new %.4f old %.4f' % (n[0], o[0], n[2], o[2], n[4], o[4], n[3], o[3], n[6], o[6]))
    if n[0] > .55: print('BAD: звёзды не прозрачнее (пик ≤ 0,55)'); bad += 1
    if n[2] > 100: print('BAD: рывок фронта (ускорение ≤ 100)'); bad += 1
    if n[4] > .2: print('BAD: звезда возникает рывком (шаг яркости за кадр ≤ 0,2)'); bad += 1
    if n[3] > .15: print('BAD: столб вспыхивает рывком (шаг ≤ 0,15)'); bad += 1
    if n[6] > .003: print('BAD: кольцо цели граненое (прогиб ≤ 0,003 радиуса)'); bad += 1
    return bad
def frames(nd, od, wd):
    names = ['e%02d' % i for i in range(10)] + ['e_end']; ro = []; rn = []; bad = 0
    for n in names:
        try: none = load(nd, n); go = np.abs(load(od, n) - none).sum(axis=2); gn = np.abs(load(wd, n) - none).sum(axis=2)
        except Exception as e: print('нет снимка', n, e); return 1
        go[:60] = 0; gn[:60] = 0; mo, mn = go > 12, gn > 12
        ro.append(go[mo].sum()); rn.append(gn[mn].sum())
    to, tn = float(sum(ro)), float(sum(rn))
    print('звёзды цели: масса по кадрам входа new/old %.2f (old %d, new %d)' % (tn / max(to, 1), to, tn))
    if to < 5000: print('BAD: у прежнего звёзд на кадрах не найдено'); bad += 1
    if not .15 <= tn / max(to, 1) <= .6: print('BAD: звёзды не вдвое прозрачнее (масса new/old .15..0,6)'); bad += 1
    return bad
def ring(ns, os_):
    def sides(f):
        r = []
        for l in open(f, errors='ignore'):
            m = re.match(r'SPHERE976 name=\S+ sides=(\d+) far=(\d) old=(\d)', l)
            if m and m[2] == '0': r.append(int(m[1]))
        return r
    n, o = sides(ns), sides(os_); print('сторон кольца у цели вблизи: new %s old %s' % (sorted(set(n)), sorted(set(o))))
    bad = 0
    if not n or max(n) < 40: print('BAD: у нового кольца меньше 40 сторон'); bad += 1
    if not o or max(o) > 20: print('BAD: прежнее кольцо не 18 сторон'); bad += 1
    return bad
if __name__ == '__main__':
    m = sys.argv[1]; bad = {'host': host, 'frames': frames, 'ring': ring}[m](*sys.argv[2:5 if m == 'frames' else 4])
    print('FAIL' if bad else 'PASS'); sys.exit(1 if bad else 0)
