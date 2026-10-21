#!/usr/bin/env python3
"""Проход A против прохода B по шести счетам учёта ACCT (viewer/acct.h) с порогом шума.
  python3 tools/acct_ab.py A/acct.txt B/acct.txt [--same СЦЕНА1,СЦЕНА2] [--k 2.0] [--out файл.md]
Порог шума берётся из двух ОДИНАКОВЫХ отрезков одного прохода A: сцены, перечисленные в --same (по умолчанию пары с именами X и X2, X_a и X_b,
иначе две половины самой длинной сцены). Шум метрики = |среднее первого - среднее второго|, не меньше абсолютного пола; различие A и B значимо,
если |ΔB-A| > k × шум (k=2) и больше пола. Счета: B построение, L подгрузка, D делегирование, M ME, S свет, H куча.
Выход: 0 — значимых различий нет, 1 — есть (в таблице видно, по какому счёту)."""
import re, sys, argparse
from collections import defaultdict

FLOOR = {'w': .15, 'wmax': 1.0, 'cpu': .15, 'ge': .15, 'calls': 8, 'kt': .5, 'draws': 10, 'binds': 4, 'lq': 0.5, 'late': 1, 'loads': 5, 'bad': 0.5, 'rd_ms': 5, 'lat': 10, 'slow': 1,
         'd0': 2, 'd1': 2, 'd2': 2, 'd3': 2, 'd4': 2, 'mok': 3, 'msaved': 40, 'free': .2, 'blk': .3, 'acct_us': 100}
ACC = {'B построение': ['w', 'wmax', 'cpu', 'ge', 'calls', 'kt', 'draws', 'binds'], 'L подгрузка': ['lq', 'late', 'loads', 'bad', 'rd_ms', 'lat', 'slow'],
       'D делегирование': ['d0', 'd1', 'd2', 'd3', 'd4'], 'M ME': ['mok', 'msaved'], 'H куча': ['free', 'blk'], 'учёт': ['acct_us']}


def num(s, d=0.0):
    try: return float(s)
    except Exception: return d


def parse(path):
    rows = defaultdict(list)
    for ln in open(path, errors='replace'):
        if not ln.startswith('ACCT '): continue
        m = re.search(r'sc=(\S+)', ln)
        if not m: continue
        r = {}
        for k, v in re.findall(r'\b(w|wmax|cpu|ge|calls|kt|draws|binds|lq|late|loads|bad|rd_ms|lat|slow|free|blk|acct_us)=([\d.\-]+)', ln): r[k] = num(v)
        d = re.search(r'\| D (\d+)/(\d+)/(\d+)/(\d+)/(\d+)', ln)
        if d:
            for i in range(5): r[f'd{i}'] = num(d.group(i + 1))
        mm = re.search(r'ok=(\d+)/(\d+)', ln); ms = re.search(r'saved_us=(\d+)', ln)
        if mm and int(mm.group(2)): r['mok'] = 100.0 * int(mm.group(1)) / int(mm.group(2))
        if ms: r['msaved'] = num(ms.group(1))
        rows[m.group(1)].append(r)
    return rows


def mean(rs, k):
    v = [r[k] for r in rs[2:] if k in r] or [r[k] for r in rs if k in r]   # без первых двух секунд сцены (прогрев)
    return sum(v) / len(v) if v else None


def noise_pairs(A, same):
    if same: return [tuple(same[:2])] if len(same) >= 2 else []
    names = list(A)
    pairs = [(n, n + '2') for n in names if n + '2' in A] + [(n, n[:-2] + '_b') for n in names if n.endswith('_a') and n[:-2] + '_b' in A]
    if pairs: return pairs
    big = max(names, key=lambda n: len(A[n]), default=None)
    return [(big, None)] if big else []


def noise(A, pairs):
    out = defaultdict(float)
    for a, b in pairs:
        ra = A[a]; ha = ra[:len(ra) // 2] if b is None else ra; hb = ra[len(ra) // 2:] if b is None else A[b]
        for ks in ACC.values():
            for k in ks:
                x, y = mean(ha, k), mean(hb, k)
                if x is not None and y is not None: out[k] = max(out[k], abs(x - y))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('a'); ap.add_argument('b'); ap.add_argument('--same', default=''); ap.add_argument('--k', type=float, default=2.0); ap.add_argument('--out')
    o = ap.parse_args(); A, B = parse(o.a), parse(o.b)
    if not A or not B: print('в одном из файлов нет строк ACCT'); return 2
    pairs = noise_pairs(A, [x for x in o.same.split(',') if x]); nz = noise(A, pairs)
    out = [f'# Проход A против B по счетам · A={o.a} · B={o.b}', '', 'Порог шума по одинаковым отрезкам прохода A: ' + (', '.join(f'{a}~{b or "вторая половина"}' for a, b in pairs) or 'нет'), '']
    out += ['| сцена | счёт | метрика | A | B | Δ | шум A | вывод |', '|---|---|---|---|---|---|---|---|']
    sig = 0
    for sc in A:
        if sc not in B: continue
        for acc, ks in ACC.items():
            for k in ks:
                x, y = mean(A[sc], k), mean(B[sc], k)
                if x is None or y is None: continue
                d = y - x; fl = FLOOR.get(k, 0); lim = max(o.k * nz.get(k, 0), fl)
                if abs(d) > lim: sig += 1; out.append(f'| {sc} | {acc} | {k} | {x:.2f} | {y:.2f} | {d:+.2f} | {nz.get(k, 0):.2f} | **значимо** ({"хуже" if (d > 0) == (k not in ("free", "blk", "mok", "msaved")) else "лучше"}) |')
    out += ['', f'Значимых различий: {sig}. Остальное в шуме (порог {o.k:g}× шума, не ниже пола метрики).']
    txt = '\n'.join(out) + '\n'
    if o.out: open(o.out, 'w').write(txt)
    print(txt)
    return 1 if sig else 0


if __name__ == '__main__': sys.exit(main())
