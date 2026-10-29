#!/usr/bin/env python3
# №930в: проверка цены трафика в фиксированной сцене L5 (4 машины рядом). check.py gate A B ПОРОГ | cfc out_cfc out_new
#   gate A B K: на машину в окнах A не больше B*K (окна считаются после переключения заливки: две секунды перекраски отброшены); код возврата 0 — прошло
import re, sys
def per_car(fn, scene='T_L5', only_on=None):
    first = {}; on = None; skip = 0; tc = tn = 0.0; k = 0
    for l in open(fn, errors='ignore'):
        m = re.match(r'CARFILL t=([\d.]+) .*? on=(\d)', l)
        if m:
            o = int(m.group(2))
            if o != on: on = o; skip = 2
            continue
        m = re.match(r'PHSUB t=([\d.]+) scene=(\S+)', l)
        if not m: continue
        t = float(m.group(1)); sc = m.group(2); first.setdefault(sc, t)
        if sc != scene or t - first[sc] < 46: continue
        if skip > 0: skip -= 1; continue
        if only_on is not None and on != only_on: continue
        n = re.search(r'trf_n=([\d.]+)/([\d.]+)', l)
        tc += float(re.search(r'trf_cars=([\d.]+)', l).group(1)); tn += float(n.group(1)) + float(n.group(2)); k += 1
    return (tc / tn if tn else 0.0), k
if sys.argv[1] == 'gate':
    a, ka = per_car(sys.argv[2]); b, kb = per_car(sys.argv[3]); k = float(sys.argv[4])
    print('  на машину: %.4f мс Mac (%d окон) против %.4f (%d окон), отношение %.3f, порог %.2f' % (a, ka, b, kb, a / b if b else 9, k))
    sys.exit(0 if ka >= 20 and kb >= 20 and a <= b * k else 1)
if sys.argv[1] == 'fill':   # заливка включена в новой сборке против базы без заливки (CARFILL930_OLD): не дороже
    a, ka = per_car(sys.argv[2], only_on=1); b, kb = per_car(sys.argv[3]); k = float(sys.argv[4])
    print('  заливка: %.4f мс Mac на машину (%d окон) против базы %.4f (%d), отношение %.3f, порог %.2f' % (a, ka, b, kb, a / b if b else 9, k))
    sys.exit(0 if ka >= 15 and kb >= 15 and a <= b * k else 1)
if sys.argv[1] == 'cfc':   # CFCOST: с флагом считает, без флага нули
    def tot(fn):
        s = 0
        for l in open(fn, errors='ignore'):
            m = re.match(r'CFCOST t=[\d.]+ whole_n=(\d+) whole_us=(\d+) fill_n=(\d+)', l)
            if m: s += int(m.group(1)) + int(m.group(3))
        return s
    a = tot(sys.argv[2]); b = tot(sys.argv[3]); print('  CFCOST: с флагом %d отрисовок, без флага %d' % (a, b)); sys.exit(0 if a > 500 and b == 0 else 1)
