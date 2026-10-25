#!/usr/bin/env python3
"""Таблица мерцания по сценам из smoke.txt (строки FLICKB датчика flickStep, №932).
python3 flick_table.py smoke.txt [smoke2.txt ...]   -> по сцене: средние по окнам в 30 кадров
  far = площадь кадра (%), где пиксель дальше 60 м вернулся к цвету двух кадров назад при шаге >= 24 («мерцание», не движение): сумма по полосам 60-120, >120 и «без глубины» (№932б: у дальнего прохода глубина очищается, поэтому его пиксели в датчике попадают в «без глубины»; небо ровное и мерцания не даёт)
  b60/b120 — доли внутри полос; all — все полосы (кроме неба)
Режим --json: одна строка JSON на сцену (для accept60.sh)."""
import re, sys, json
RX = re.compile(r'^FLICKB t=([\d.]+) sc=(\S+) area%\(<30,30-60,60-120,>120,sky\)=([\d./]+) vis%=([\d./]+) big%=([\d./]+)')
def parse(path):
    sc = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = RX.match(ln)
        if not m: continue
        a = [float(x) for x in m.group(3).split('/')]; v = [float(x) for x in m.group(4).split('/')]
        sc.setdefault(m.group(2), []).append((a, v))
    return sc
def summarize(rows):
    n = len(rows)
    if not n: return None
    band = lambda k: sum(a[k] * v[k] / 100.0 for a, v in rows) / n          # % кадра, мерцающих пикселей в полосе
    area = lambda k: sum(a[k] for a, v in rows) / n
    far = band(2) + band(3) + band(4); allv = sum(band(k) for k in range(4))
    return dict(n=n, far=far, all=allv, b0=band(0), b30=band(1), b60=band(2), b120=band(3), a60=area(2), a120=area(3))
def main():
    js = '--json' in sys.argv; files = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = {}
    for f in files:
        for k, rows in parse(f).items():
            r = summarize(rows)
            if r: out[k] = r
    if js:
        for k, r in out.items(): print(json.dumps(dict(scene=k, **r), ensure_ascii=False))
        return
    print('%-18s %4s %8s %8s %8s %8s %8s %8s %8s' % ('scene', 'win', 'far%', 'all%', '<30', '30-60', '60-120', '>120', 'area60+'))
    for k, r in out.items():
        print('%-18s %4d %8.4f %8.4f %8.4f %8.4f %8.4f %8.4f %8.1f' % (k, r['n'], r['far'], r['all'], r['b0'], r['b30'], r['b60'], r['b120'], r['a60'] + r['a120']))
main()
