#!/usr/bin/env python3
"""Гейт памяти TEST57 В: куча и наибольший кусок на каждой сцене не ниже сборки TEST55 (tests/mem/heap57_ref.txt), отказов памяти 0.
  heap57_check.py smoke.txt [--blk-tol МБ] [--print-ref]
Числа считаются из журнала сами (не из строки STAT: у неё минимум куки переходит через границу сцены): куча — минимум секундных строк «t сцена … heapMB», кусок — минимум
«blk» строк BB, оба по секундам сцены после первых 2 с (загрузка уровня закончена). Куча — строго (прогон одной сборки воспроизводится побайтно). Кусок: в эмуляторе зависит от порядка
выделений (любая правка тасует его на ±0,7 МБ), допуск --blk-tol (по умолчанию 0,75); настоящий вердикт по куску даёт тур на PSP. Код 0 — всё в норме."""
import re, sys
args = sys.argv[1:]; tol = 0.75; pr = '--print-ref' in args
if pr: args.remove('--print-ref')
if '--blk-tol' in args: i = args.index('--blk-tol'); tol = float(args[i + 1]); del args[i:i + 2]
def scan(fn):   # по порядку строк журнала: SCENE задаёт сцену, секундная строка — время, строка BB относится к сцене и времени последней секундной строки
    heap = {}; blk = {}; fails = {}; scene = None; t0 = 0.0; tcur = 0.0
    for ln in open(fn, errors='replace'):
        m = re.match(r'SCENE (\S+) ([\d.]+)', ln)
        if m: scene = m.group(1); t0 = tcur = float(m.group(2)); continue
        p = ln.split()
        if len(p) >= 15 and p[1].startswith('F_') and re.match(r'^\d+(\.\d+)?$', p[0]):
            try: t = float(p[0]); h = float(p[14]); f = int(p[13])
            except ValueError: continue
            tcur = t
            if p[1] == scene and t >= t0 + 2: heap.setdefault(scene, []).append(h); fails[scene] = max(fails.get(scene, 0), f)
            continue
        m = re.match(r'BB\s+\d+\s.*?\bheap\s+[\d.]+\s+blk\s+([\d.]+)', ln)
        if m and scene and tcur >= t0 + 2: blk.setdefault(scene, []).append(float(m.group(1)))
    return {k: (min(heap[k]), min(blk[k]), fails.get(k, 0)) for k in heap if k in blk}
got = scan(args[0])
if pr:
    for k, (h, b, f) in got.items(): print(f'{k} {h:.2f} {b:.2f}')
    sys.exit(0)
ref = {}
for ln in open(__file__.replace('heap57_check.py', 'heap57_ref.txt')):
    p = ln.split()
    if len(p) == 3 and not ln.startswith('#'): ref[p[0]] = (float(p[1]), float(p[2]))
bad = 0
for sc, (h0, b0) in ref.items():
    if sc not in got: print(f'нет сцены {sc}'); bad += 1; continue
    h, b, f = got[sc]; bits = []
    if h + 1e-6 < h0: bits.append(f'куча {h:.2f} < {h0:.2f}')
    if b + tol + 1e-6 < b0: bits.append(f'кусок {b:.2f} < {b0:.2f} − {tol}')
    if f: bits.append(f'отказов памяти {f}')
    print(f'{sc:12} куча {h:6.2f} (TEST55 {h0:6.2f})  кусок {b:6.2f} (TEST55 {b0:6.2f})  ' + ('ПРОВАЛ: ' + '; '.join(bits) if bits else 'ok')); bad += bool(bits)
print('ИТОГ:', 'ПРОВАЛ' if bad else 'OK'); sys.exit(1 if bad else 0)
