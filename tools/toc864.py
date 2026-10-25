#!/usr/bin/env python3
# №864 (окно «Оптимизация»), пропечка 1: оглавление района. По точкам разведчика (build/scout/l<N>.csv: x, y, z) и клеткам level.shr считает для каждой точки, что надо держать
# в памяти вокруг неё: клетки в радиусе загрузки (дальность + 75 м, как LOAD_DIST), их байты, число различных текстур, стоящие машины трафика (traffic.shr, TrPark) рядом. Точки собираются в районы
# (сетка BIN м); для района — худшая точка. Пишет toc864-l<N>.json (таблица районов) и отчёт «где район не влезает в память»: свободная куча в районе ≈ куча на старте уровня (--heap-mb, замер гейта
# tests/mem при клетках старта) − (клетки района − клетки старта); не влезает, если ниже MEM_RESERVE + запас.
#   python3 tools/toc864.py LEVEL.shr SCOUT.csv TRAFFIC.shr OUT.json --spawn X,Z [--dd 150] [--heap-mb 14.2] [--report]
import sys, struct, json, math, csv, argparse
import numpy as np
MEM_RESERVE_MB = 3.0
SLACK_MB = 1.5      # запас на всё прочее живое (трафик, пешеходы, звук, миссии)
BIN = 64.0

def load_level(path):
    with open(path, 'rb') as f:
        h = f.read(104)
        npc = struct.unpack_from('<I', h, 8)[0]
        tableOff, ncell, cellOff = struct.unpack_from('<III', h, 76)
        f.seek(cellOff); b = f.read(48 * ncell)
        f.seek(tableOff); pt = f.read(80 * npc)
    a = np.frombuffer(b, dtype=np.uint8).reshape(ncell, 48)
    bb = a[:, :24].copy().view('<f4').reshape(ncell, 6)
    size = a[:, 24:48].copy().view('<u4').reshape(ncell, 6)[:, 4].astype(np.int64)
    owner = a[:, 24:48].copy().view('<u4').reshape(ncell, 6)[:, 2]
    p = np.frombuffer(pt, dtype=np.uint8).reshape(npc, 80)
    tex = p[:, 24:28].copy().view('<i4').ravel()
    return bb, size, owner, tex, p

def parks(path):
    d = open(path, 'rb').read()
    nPark, offPark = struct.unpack_from('<2I', d, 4 * 35)   # TrHeader: nPark, offPark — 35-е и 36-е слова
    if not nPark or offPark + 32 * nPark > len(d): return np.zeros((0, 2))
    r = np.frombuffer(d, dtype='<f4', count=8 * nPark, offset=offPark).reshape(nPark, 8)
    return r[:, [0, 2]].astype(np.float64)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('scout'); ap.add_argument('traffic'); ap.add_argument('out')
    ap.add_argument('--spawn', default='0,0'); ap.add_argument('--dd', type=float, default=150.0); ap.add_argument('--heap-mb', type=float, default=14.0); ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    bb, size, owner, tex, pieces = load_level(a.level)
    cx = (bb[:, 0] + bb[:, 3]) * .5; cy = (bb[:, 1] + bb[:, 4]) * .5; cz = (bb[:, 2] + bb[:, 5]) * .5
    rad = np.sqrt(((bb[:, 3] - bb[:, 0]) * .5) ** 2 + ((bb[:, 4] - bb[:, 1]) * .5) ** 2 + ((bb[:, 5] - bb[:, 2]) * .5) ** 2)
    pk = parks(a.traffic)
    loadD = a.dd + 75.0
    pts = []
    with open(a.scout) as f:
        for r in csv.DictReader(f): pts.append((float(r['x']), float(r['y']), float(r['z'])))
    pts = np.array(pts)
    sx, sz = (float(v) for v in a.spawn.split(','))
    ds = np.sqrt((cx - sx) ** 2 + (cz - sz) ** 2) - rad
    spawn_mb = float(size[ds < a.dd + 75.0].sum()) / 1048576.0   # клетки старта (при дальности 150)
    budget = a.heap_mb - MEM_RESERVE_MB - SLACK_MB + spawn_mb   # сколько МБ клеток можно держать вокруг точки
    # дальнего света хватает: считаем по центрам клеток
    res = {}
    for (x, y, z) in pts:
        d = np.sqrt((cx - x) ** 2 + (cy - y) ** 2 + (cz - z) ** 2) - rad
        m = d < loadD
        mb = float(size[m].sum()) / 1048576.0
        npk = int((((pk[:, 0] - x) ** 2 + (pk[:, 1] - z) ** 2) < loadD * loadD).sum()) if len(pk) else 0
        key = (int(math.floor(x / BIN)), int(math.floor(z / BIN)))
        cur = res.get(key)
        if cur is None or mb > cur['mb']:
            res[key] = dict(gx=key[0], gz=key[1], x=round(float(x), 1), z=round(float(z), 1), cells=int(m.sum()), mb=round(mb, 2), parked=npk)
    rows = sorted(res.values(), key=lambda r: -r['mb'])
    over = [r for r in rows if r['mb'] > budget]
    out = dict(spawn_mb=round(spawn_mb, 2), level=a.level.split('/')[-2] if '/' in a.level else a.level, dd=a.dd, loadD=loadD, budget_mb=round(budget, 2), heap_mb=a.heap_mb, bin_m=BIN,
               districts=len(rows), over=len(over), mb_p50=round(float(np.percentile([r['mb'] for r in rows], 50)), 2), mb_p95=round(float(np.percentile([r['mb'] for r in rows], 95)), 2), mb_max=rows[0]['mb'], rows=rows)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False)
    print(f"TOC864 spawn={spawn_mb:.1f} MB districts={len(rows)} points={len(pts)} loadD={loadD:.0f} budget={budget:.1f} MB: p50={out['mb_p50']} p95={out['mb_p95']} max={out['mb_max']} MB, не влезают {len(over)}")
    if a.report:
        for r in over[:8]: print(f"  район ({r['x']:.0f}, {r['z']:.0f}): клеток {r['cells']}, {r['mb']} МБ > бюджет {budget:.1f}, стоящих машин {r['parked']}")

main()
