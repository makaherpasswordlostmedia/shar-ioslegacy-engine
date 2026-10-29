#!/usr/bin/env python3
"""Сводка долгой кампании роя (пункт 5 docs/handoff/LOOP_TERMINAL.md): где машины проваливаются и застревают.
Только чтение кампании и повторы её же бинарником; код движка не меняется, без AI и сети.

  python3 tools/cartest/soak_report.py [--soak build/sandbox/soaks/20260927-175304-ded22e] [--top 20] [--no-replay]
  -> build/sandbox/soak-report.json + build/sandbox/soak-report.png

Кластеры: сетка 8 м по XZ; виды событий: penetration (кузов в мире >= 0.15 м 12 тиков подряд), long-flight (5 с без
опоры), blocked-review (10 с стоит у стены), recovery (возврат на надёжное место). На каждое место из топа — один повтор
(seed, машина, тик, команда) и класс по повтору той же кампанией: «машина-машина» (другая машина ближе 6 м в тике события
или за 0.5 с до него), «после приземления» (машина за 0.5 с до события была в воздухе), иначе «машина-мир».
Происхождение (станок С0, Роб 28.09): «естественное» — машина стартовала на дороге (в событии start = -1), «стресс» — старт на
случайной опоре, крыше, подброс или падение (start >= 0). Топ и числа приёмки — только естественные; стресс отдельной строкой.
"""
import argparse
import collections
import concurrent.futures
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
KINDS = ('penetration', 'long-flight', 'blocked-review', 'recovery')
CELL = 8.0


def events_of(trace):
    out = []
    with open(trace, 'rb') as f:
        for line in f:
            if line.startswith(b'{"type":"event"'):
                e = json.loads(line)
                if e['kind'] in KINDS:
                    out.append(e)
    return out


def final_frame(swarm, soak, seed, ticks):
    cmd = [str(swarm), '--level', str(soak / 'level.shr'), '--roads', str(soak / 'roads.bin'), '--cars', '256',
           '--seed', str(seed), '--ticks', str(max(1, ticks)), '--emit', '600']
    last = None
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    for line in p.stdout.splitlines():
        if line.startswith('{"type":"frame"'):
            last = line
    return json.loads(last) if last else None


def classify(soak, ev):
    swarm = soak / 'swarm'
    fr_t = final_frame(swarm, soak, ev['seed'], ev['tick'])
    fr_b = final_frame(swarm, soak, ev['seed'], ev['tick'] - 30)
    if not fr_t or not fr_b:
        return dict(cls='повтор не удался')
    def near(fr):
        cars = {c[0]: c for c in fr['cars']}
        me = cars.get(ev['car'])
        if not me:
            return None, 99.0
        best = 99.0
        for k, c in cars.items():
            if k != ev['car']:
                best = min(best, math.dist((me[1], me[3]), (c[1], c[3])))
        return me, best
    me_t, d_t = near(fr_t)
    me_b, d_b = near(fr_b)
    if me_t is None:
        return dict(cls='повтор не удался')
    replayed = math.dist((me_t[1], me_t[2], me_t[3]), tuple(ev['xyz'])) < 1.0   # тот же исход в тот же тик
    airborne_before = bool(me_b and (int(me_b[9]) & 1))
    cls = 'машина-машина' if min(d_t, d_b) < 6.0 else ('после приземления' if airborne_before else 'машина-мир')
    return dict(cls=cls, replayed=replayed, nearestCarM=round(min(d_t, d_b), 2), airborneHalfSecondBefore=airborne_before)


def draw(soak, cells, top, out_png):
    import sys
    import numpy as np
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / 'tools'))
    from col_check import load, parse_col
    b, L = load(str(soak / 'level.shr')); C = parse_col(b, L['col']); s = 1.0
    x0, z0 = C['ox'], C['oz']; W, H = int(C['W'] * C['cell'] * s), int(C['H'] * C['cell'] * s)
    img = Image.new('RGB', (W, H), (15, 15, 18)); d = ImageDraw.Draw(img)
    P = lambda x, z: ((x - x0) * s, (z - z0) * s)
    T = C['tri']; ys = T[:, :3, 1].mean(1); lo, hi = np.percentile(ys, 2), np.percentile(ys, 98)
    for t, y in zip(T, ys):
        g = int(35 + 90 * np.clip((y - lo) / (hi - lo), 0, 1))
        d.polygon([P(t[k, 0], t[k, 2]) for k in range(3)], fill=(g, g, g) if t[3, 1] > .5 else (90, 40, 40))
    col = {'penetration': (255, 60, 60), 'long-flight': (80, 160, 255), 'blocked-review': (255, 210, 40), 'recovery': (200, 90, 255)}
    for (cx, cz), c in cells.items():
        if not c['kinds']: continue                                   # только стресс — на карте приёмки не рисуем
        k = max(c['kinds'], key=c['kinds'].get); n = sum(c['kinds'].values())
        r = 1 + min(6, math.log2(1 + n / 50))
        u, v = P(cx * CELL + CELL / 2, cz * CELL + CELL / 2)
        d.ellipse([u - r, v - r, u + r, v + r], fill=col[k])
    for i, t in enumerate(top, 1):
        u, v = P(t['x'], t['z'])
        d.ellipse([u - 9, v - 9, u + 9, v + 9], outline=(255, 255, 255), width=2)
        d.text((u + 11, v - 7), str(i), fill=(255, 255, 255))
    img.save(out_png)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--soak', type=Path, default=ROOT / 'build/sandbox/soaks/20260927-175304-ded22e')
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--no-replay', action='store_true')
    ap.add_argument('--out', type=Path, default=ROOT / 'build/sandbox/soak-report.json')
    a = ap.parse_args()
    soak = a.soak.resolve(); a.out = a.out.resolve()
    done = sorted(soak.glob('complete-*.json'))
    if not done:
        raise SystemExit('нет complete-*.json в ' + str(soak))
    runs = [json.loads(p.read_text()) for p in done]
    cells = collections.defaultdict(lambda: dict(kinds=collections.Counter(), seeds=set(), ev=None, stress=0))
    totals, stress = collections.Counter(), collections.Counter()
    perSeed = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for r, evs in zip(runs, ex.map(lambda r: events_of(soak / r['trace']), runs)):
            nat = perSeed.setdefault(r['seed'], collections.Counter())
            for e in evs:
                x, y, z = e['xyz']
                if e.get('start', -1) >= 0:                            # стресс-старт: в приёмку не идёт
                    stress[e['kind']] += 1; cells[(math.floor(x / CELL), math.floor(z / CELL))]['stress'] += 1; continue
                nat[e['kind']] += 1
                c = cells[(math.floor(x / CELL), math.floor(z / CELL))]
                c['kinds'][e['kind']] += 1; c['seeds'].add(r['seed']); totals[e['kind']] += 1
                cand = dict(e, seed=r['seed'])
                if c['ev'] is None or (cand['seed'], cand['tick']) < (c['ev']['seed'], c['ev']['tick']):
                    c['ev'] = cand
    n = len(runs)
    ranked = sorted([kv for kv in cells.items() if kv[1]['ev']], key=lambda kv: -sum(kv[1]['kinds'].values()))
    top = []
    for (cx, cz), c in ranked[:a.top]:
        e = c['ev']
        cmd = '%s --level %s --roads %s --cars 256 --seed %d --ticks %d --emit 1' % (
            (soak / 'swarm').relative_to(ROOT), (soak / 'level.shr').relative_to(ROOT), (soak / 'roads.bin').relative_to(ROOT),
            e['seed'], e['tick'] + 1)
        top.append(dict(x=cx * CELL + CELL / 2, z=cz * CELL + CELL / 2, events=sum(c['kinds'].values()),
                        perSeries=round(sum(c['kinds'].values()) / n, 3), kinds=dict(c['kinds']), seeds=len(c['seeds']),
                        replay=dict(seed=e['seed'], car=e['car'], tick=e['tick'], kind=e['kind'], xyz=e['xyz'], command=cmd)))
    if not a.no_replay:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            for t, k in zip(top, ex.map(lambda t: classify(soak, t['replay']), top)):
                t['class'] = k
    by_class = collections.Counter(t.get('class', {}).get('cls', 'не классифицировано') for t in top)
    rep = dict(kind='soak-report-v2', soak=str(soak.relative_to(ROOT)), series=n, cellM=CELL, origin='естественное (старт на дороге)',
               perSeries={k: round(totals[k] / n, 2) for k in KINDS}, totals=dict(totals), cells=len(cells),
               stressPerSeries={k: round(stress[k] / n, 2) for k in KINDS}, stressTotals=dict(stress),
               perSeedNatural={str(sd): dict(c) for sd, c in sorted(perSeed.items())},
               top=top, topByClass=dict(by_class),
               allCells=[[cx, cz] + [c['kinds'].get(k, 0) for k in KINDS] + [len(c['seeds']), c['stress']]
                         for (cx, cz), c in sorted(cells.items())],
               allCellsColumns=['cellX', 'cellZ', *KINDS, 'seeds', 'stressEvents'],
               note='наблюдения роя на Mac, не приёмка; повтор: бинарник и данные из папки кампании, тот же seed, весь флот')
    tmp = a.out.with_suffix('.json.tmp'); tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1)); tmp.replace(a.out)
    draw(soak, cells, top, a.out.with_suffix('.png'))
    print('серий %d, естественные на серию: %s; стресс на серию: %s; мест %d; топ-%d по классам: %s' % (n,
          ' '.join('%s %.1f' % (k, totals[k] / n) for k in KINDS), ' '.join('%s %.1f' % (k, stress[k] / n) for k in KINDS),
          len(cells), len(top), dict(by_class)))
    print('отчёт: %s, карта: %s' % (a.out.relative_to(ROOT), a.out.with_suffix('.png').relative_to(ROOT)))
    return rep


if __name__ == '__main__':
    main()
