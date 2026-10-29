#!/usr/bin/env python3
# №864 пропечка 2 (загрузка вдоль дороги): метрики езды по smoke.txt безголового тура (сцены F_D<N>_L<N>: стоим 12 с, едем автопилотом 70 с).
#   roadq_metrics.py smoke.txt              -> таблица по сценам
#   roadq_metrics.py smoke_new smoke_old    -> сравнение; код возврата 1, если у нового хуже
# Метрики (меньше — лучше): missvis — кадров с видимой незагруженной клеткой (строка STAT), миссов MISSCELL за езду и средняя «поздняя» дальность (d, м: чем дальше от глаза пропуск, тем он заметнее
# при въезде), загрузок клеток за езду (STREAMCOST loads), загрузок «стоя» (первые 12 с сцены после 4 с прогрева), p95 кадра.
import sys, re, collections

def parse(fn):
    sc = collections.OrderedDict(); cur = None; t0 = {}; last_loads = {}
    for ln in open(fn, errors='replace'):
        if ln.startswith('SCENE '):
            p = ln.split(); cur = p[1]; t0[cur] = float(p[2]) if len(p) > 2 else 0.0
            sc[cur] = dict(miss=0, missd=[], stand=0, drive=0, missvis=0, missvismax=0, p95=0.0, max=0.0, rq=(0, 0, 0), loads0=None, loadsStand=None, loadsEnd=None)
            continue
        if cur is None: continue
        s = sc[cur]
        if ln.startswith('MISSCELL '):
            m = re.search(r' d=(\d+) ', ln); tm = re.search(r' t=([\d.]+)', ln)
            if m and tm and float(tm.group(1)) - t0[cur] >= 4.0:
                s['miss'] += 1; s['missd'].append(int(m.group(1)))
        elif ln.startswith('STREAMCOST '):
            m = re.search(r'loads=(\d+)', ln); tm = re.search(r' t=([\d.]+)', ln); rq = re.search(r'rq=(\d+)/(\d+)/(\d+)', ln)
            if m and tm:
                n = int(m.group(1)); tt = float(tm.group(1)) - t0[cur]
                if s['loads0'] is None and tt >= 4.0: s['loads0'] = n
                if tt <= 12.5: s['loadsStand'] = n
                s['loadsEnd'] = n
                if rq: s['rq'] = tuple(int(v) for v in rq.groups())
        elif ln.startswith('STAT ') and ln.split()[1] == cur:
            for k, key in (('missvis', 'missvis'), ('missvismax', 'missvismax')):
                m = re.search(r' %s (\d+)' % k, ln)
                if m: s[key] = int(m.group(1))
            for k in ('p95', 'max'):
                m = re.search(r' %s ([\d.]+)' % k, ln)
                if m: s[k] = float(m.group(1))
    for s in sc.values():
        a, b, c = s['loads0'], s['loadsStand'], s['loadsEnd']
        s['stand'] = (b - a) if a is not None and b is not None and b >= a else 0
        s['drive'] = (c - b) if b is not None and c is not None and c >= b else 0
    return sc

def table(sc):
    print(f"{'сцена':10} {'missvis':>8} {'max':>4} {'MISSCELL':>9} {'d среднее':>9} {'загр.езда':>9} {'загр.стоя':>9} {'p95':>6}  rq кадров/клеток/в очереди")
    for k, s in sc.items():
        d = sum(s['missd']) / len(s['missd']) if s['missd'] else 0.0
        print(f"{k:10} {s['missvis']:8d} {s['missvismax']:4d} {s['miss']:9d} {d:9.0f} {s['drive']:9d} {s['stand']:9d} {s['p95']:6.2f}  {s['rq'][0]}/{s['rq'][1]}/{s['rq'][2]}")

if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 1: table(parse(a[0])); sys.exit(0)
    n, o = parse(a[0]), parse(a[1]); bad = 0
    print(f"{'сцена':10} | {'missvis новый/старый':>20} | {'MISSCELL':>12} | {'загр.езда':>12} | {'загр.стоя':>12} | вердикт")
    tn = [0, 0, 0, 0]; to = [0, 0, 0, 0]
    for k in n:
        if k not in o: continue
        x, y = n[k], o[k]
        v = (x['missvis'], x['miss'], x['drive'], x['stand']); w = (y['missvis'], y['miss'], y['drive'], y['stand'])
        for i in range(4): tn[i] += v[i]; to[i] += w[i]
        ok = v[0] <= w[0] + 2 and v[1] <= w[1] + 2
        if not ok: bad += 1
        print(f"{k:10} | {v[0]:9d} /{w[0]:9d} | {v[1]:5d} /{w[1]:5d} | {v[2]:5d} /{w[2]:5d} | {v[3]:5d} /{w[3]:5d} | {'ok' if ok else 'ХУЖЕ'}")
    print(f"{'сумма':10} | {tn[0]:9d} /{to[0]:9d} | {tn[1]:5d} /{to[1]:5d} | {tn[2]:5d} /{to[2]:5d} | {tn[3]:5d} /{to[3]:5d} |")
    sys.exit(1 if bad or tn[0] + tn[1] > to[0] + to[1] else 0)
