#!/usr/bin/env python3
"""Цена мировой ленты в езде (№934): строки HORIZON cost из smoke.txt прогона cost_scn.sh (лента переключается мировая/прежняя каждые 6 с в одной езде).
Берём окна, где машина едет (builds > 0 у мировой, у прежней — окна между переключениями), медиана avg_us на режим; дельта × 5,8 (Мак → PSP) должна быть ≤ LIM мкс (по умолчанию 200); число вершин ленты в кадре (цена GE, эмулятор её не меряет) мировая / прежняя ≤ VLIM (1,6).
Отрицательная дельта — мировая лента дешевле прежней (вершин 600–800 против 1100–1400: у прежней добавлялись промежуточные вершины хорд).
  cost.py smoke.txt [--lim 200] [--k 5.8]    код 0 = PASS"""
import sys, re, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('f'); ap.add_argument('--lim', type=float, default=200.); ap.add_argument('--k', type=float, default=5.8); ap.add_argument('--vlim', type=float, default=1.6); a = ap.parse_args()
w = {0: [], 1: []}; wus = []; bld = []; vt = {0: [], 1: []}
for ln in open(a.f, errors='replace'):
    if not ln.startswith('HORIZON cost'): continue
    m = dict(re.findall(r'(\w+)=(-?\d+)', ln)); k = int(m['world']); w[k].append(int(m['avg_us'])); vt[k].append(int(m['verts']))
    if k: bld.append(int(m['builds'])); wus.append(int(m['wus']))
w1 = [x for x, b in zip(w[1], bld) if b > 0]
if len(w1) < 4 or len(w[0]) < 4: print('мало окон: мировая в езде %d, прежняя %d' % (len(w1), len(w[0]))); print('HZ934-ЦЕНА: FAIL'); sys.exit(1)
m1, m0 = float(np.median(w1)), float(np.median(w[0])); d = (m1 - m0) * a.k
pb = [(b * u) / 30. for b, u in zip(bld, wus) if b > 0]
print('мировая (окна с пересчётом, %d): медиана %.0f мкс, прежняя (%d окон): медиана %.0f мкс; вершин в кадре %d против %d' % (len(w1), m1, len(w[0]), m0, np.median(vt[1]), np.median(vt[0])))
print('пересчёт: %.0f мкс на сборку, %.1f сборок на 30 кадров, в среднем %.1f мкс на кадр (Мак)' % (np.median([u for u, b in zip(wus, bld) if b > 0]), np.mean([b for b in bld if b > 0]), np.mean(pb)))
vr = float(np.median(vt[1])) / max(1., float(np.median(vt[0])))
print('дельта %.0f мкс Мак × %.1f = %.0f мкс PSP (предел %.0f); вершин мировая / прежняя = %.2f (предел %.1f: цена GE по вершинам, эмулятор её не меряет)' % (m1 - m0, a.k, d, a.lim, vr, a.vlim)); ok = d <= a.lim and vr <= a.vlim
print('HZ934-ЦЕНА: %s' % ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)
