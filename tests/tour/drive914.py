#!/usr/bin/env python3
# №914: гейт служебного автопилота (flag drive N). По журналу smoke.txt, на каждую сцену с PILOT start:
#   время езды (PILOT end t − PILOT start t) = заданному N ± 0,2 с, путь (dist в PILOT end) > 0 и не меньше --min м.
# --walk: то же для flag walk (строки PILOT walk start/end, режим 5), срок задан = прошло ± 0,2 с.
# Красный контроль: прогон с flag adclockold 1 / adseatold 1 (прежний код) — python3 drive914.py smoke.txt --expect fail
import re, sys
args = [a for a in sys.argv[1:] if not a.startswith('--')]
expect = 'fail' if '--expect' in sys.argv and sys.argv[sys.argv.index('--expect') + 1] == 'fail' else 'pass'
if expect == 'fail': args = [a for a in args if a != 'fail']
mn = float(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 30.0
W = 'walk ' if '--walk' in sys.argv else ''
if args and args[-1] == str(mn): args = args[:-1]
sc, rows, cur, seat = None, [], None, None
for ln in open(args[0], errors='replace'):
    m = re.match(r'SCENE (\S+)', ln)
    if m: sc = m.group(1); continue
    m = re.search(r'PILOT ' + W + r'start t=([\d.]+) secs=([\d.]+)', ln)
    if m: cur = {'sc': sc, 't0': float(m.group(1)), 'secs': float(m.group(2)), 'seat': seat, 't1': None, 'dist': None}; seat = None; rows.append(cur); continue
    m = re.search(r'PILOT seat from=(\S+) to=(\S+)', ln)
    if m: seat = (m.group(1), m.group(2)); continue
    m = re.search(r'PILOT ' + W + r'end t=([\d.]+) dist=(\d+)', ln)
    if m and cur and cur['t1'] is None: cur['t1'] = float(m.group(1)); cur['dist'] = int(m.group(2))
bad = 0
print('%-8s %6s %7s %6s  %s' % ('сцена', 'задано', 'ехал', 'путь', 'посадка'))
for r in rows:
    ok = r['t1'] is not None and abs((r['t1'] - r['t0']) - r['secs']) <= 0.2 and r['dist'] is not None and r['dist'] > 0 and r['dist'] >= mn
    run = (r['t1'] - r['t0']) if r['t1'] is not None else -1
    print('%-8s %6.1f %7.1f %5s м  %s  %s' % (r['sc'], r['secs'], run, r['dist'], r['seat'] and '%s -> %s' % r['seat'] or '-', 'OK' if ok else 'НАРУШЕНИЕ'))
    bad += not ok
if not rows: print('PILOT start не найден'); bad = 1
res = 'PASS' if bad == 0 else 'FAIL'
print(res, '(%d сцен, нарушений %d)' % (len(rows), bad))
sys.exit(0 if (res == 'PASS') == (expect == 'pass') else 1)
