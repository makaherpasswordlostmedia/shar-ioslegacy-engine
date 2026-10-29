#!/usr/bin/env python3
"""Перепись стен: рой tools/cartest/walls.c на ядрах Мака, сводка «где упирается и видно ли это на картинке».
Просьба Роба 28.09: «если оно прозрачное, почему оно не даёт проехать»; объяснение логикой игры — отдельно, баг — чинить.
  python3 tools/cartest/walls.py [--procs 7] [--minutes 10] [--cars 256]      рой -> build/sandbox/walls/<время>/
  python3 tools/cartest/walls.py --gate                                         отрицательный контроль классификатора
Семейства в сводке:
  граница     забор 0x3000000 из *_terra (невидим по замыслу оригинала, закон 3 очереди: настоящая граница карты)
  видимая     горизонтальные лучи 0.4..1.4 м над полом упираются в нарисованное не дальше 1 м за точкой удара
  прозрачная  на картинке пусто: лучи ничего не нашли и нарисованная земля за точкой выше пола меньше чем на 0.3 м
  ступень     лучи ничего не нашли, но нарисованная земля за точкой выше пола на 0.3 м и больше (склон/край)
  дыра        отмена подшага «край мира» (16), а нарисованная земля под следующим положением есть
Имена исходных объектов — tools/cartest/colnames.py (сверено с COL1 level.shr). Повтор любого кластера:
  build/walls --level L --roads R --seed S --replay CAR EPOCH (события той машины за эпоху, строки ev)."""
import argparse, collections, concurrent.futures, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = [ROOT / 'tools/cartest/walls.c', ROOT / 'tools/cartest/cartest.c'] + [ROOT / 'viewer' / f for f in ('car.c', 'col.c', 'props.c', 'stateprops.c', 'coins.c', 'car.h', 'col.h')]
COLS = 'kind pt pi n nvis nflat nprop vsum vmax seed car epoch tick x y z nx nz top rise nNat carN epochN tickN'.split()


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def build(out):
    b = out / 'walls'
    subprocess.run(['cc', '-std=c99', '-O2', str(SRC[0])] + [str(p) for p in SRC[2:7]] + ['-lm', '-o', str(b)], check=True)
    return b


def swarm(binary, level, roads, seeds, cars, secs, extra=()):
    def one(s):
        r = subprocess.run([str(binary), '--level', str(level), '--roads', str(roads), '--seed', str(s), '--cars', str(cars), '--secs', str(secs), *extra],
                           capture_output=True, text=True, check=True)
        return r.stdout
    with concurrent.futures.ThreadPoolExecutor(len(seeds)) as ex:
        outs = list(ex.map(one, seeds))
    cl, st = {}, []
    for o in outs:
        for l in o.splitlines():
            f = l.split('\t')
            if f[0] == 'st': st.append(dict(seed=int(f[1]), cars=int(f[2]), carSec=float(f[3]), km=float(f[4]), wall=int(f[5]), edge16=int(f[6]), edge32=int(f[7]), push1=int(f[8])))
            if f[0] != 'cl': continue
            r = dict(zip(COLS, f[1:]))
            for k in ('pt', 'n', 'nvis', 'nflat', 'nprop', 'seed', 'car', 'epoch', 'tick', 'nNat', 'carN', 'epochN', 'tickN'): r[k] = int(r[k])
            if r['nNat']: r['seedN'] = r['seed']
            for k in ('vsum', 'vmax', 'x', 'y', 'z', 'nx', 'nz', 'top', 'rise'): r[k] = float(r[k])
            r['pi'] = int(r['pi'])
            key = (r['kind'], r['pt'], r['pi']) if r['kind'] == 'wall' else (r['kind'], int(r['x'] // 4), int(r['z'] // 4), int(r['y'] // 3))
            c = cl.get(key)
            if not c: cl[key] = r; continue
            for k in ('n', 'nvis', 'nflat', 'nprop', 'vsum', 'nNat'): c[k] += r[k]
            if r['nNat'] and 'seedN' not in c:
                for k in ('seedN', 'carN', 'epochN', 'tickN'): c[k] = r[k]
            if r['vmax'] > c['vmax']:
                for k in ('vmax', 'seed', 'car', 'epoch', 'tick', 'x', 'y', 'z', 'nx', 'nz', 'top', 'rise'): c[k] = r[k]
    return cl, st


def col_box(level, i):
    """центр xz и радиус, покрывающий ящик i COL1 (+2 м)"""
    import struct
    b = Path(level).read_bytes(); co = struct.unpack_from('<I', b, 92)[0]; ntri = struct.unpack_from('<I', b, co + 24)[0]
    r = struct.unpack_from('<16f', b, co + 48 + 48 * ntri + 64 * i); c, A, h = r[0:3], (r[3:6], r[6:9], r[9:12]), r[12:15]
    ex = sum(abs(A[k][0]) * h[k] for k in range(3)); ez = sum(abs(A[k][2]) * h[k] for k in range(3))
    return c[0], c[2], (ex * ex + ez * ez) ** .5 + 2


def family(c, names):
    if c['kind'] == 'edge16':
        return 'дыра' if c['nvis'] * 2 > c['n'] else 'край'
    if c['kind'] != 'wall':
        return c['kind']
    if c['pt'] == 3: return 'граница'
    if c['nvis'] * 2 >= c['n']: return 'видимая'
    return 'прозрачная' if c['nflat'] * 2 > c['n'] else 'ступень'


def src_name(c, names):
    if c['kind'] != 'wall': return ''
    if c['pt'] == 1: nm, sc = names['box'][c['pi']]; return f'{sc}/{nm}'
    if c['pt'] == 2: nm, sc = names['cyl'][c['pi']]; return f'{sc}/{nm}'
    return {0: 'земля (треугольник)', 3: 'забор-граница'}.get(c['pt'], '?')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=Path, default=ROOT / 'build/level.shr'); ap.add_argument('--roads', type=Path, default=ROOT / 'build/sandbox/roads-l1.bin')
    ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 4) - 3)); ap.add_argument('--minutes', type=float, default=10)
    ap.add_argument('--seconds', type=int, help='fixed simulation length for before/after comparisons'); ap.add_argument('--out', type=Path); ap.add_argument('--level-id', type=int, default=1)
    ap.add_argument('--cars', type=int, default=256); ap.add_argument('--seed0', type=int, default=1000); ap.add_argument('--gate', action='store_true')
    a = ap.parse_args()
    stamp = time.strftime('%Y%m%d-%H%M%S'); out = a.out or ROOT / 'build/sandbox/walls' / (stamp + ('-gate' if a.gate else '')); out.mkdir(parents=True, exist_ok=True)
    binary = build(out)
    subprocess.run([sys.executable, str(ROOT / 'tools/cartest/colnames.py'), '--level-shr', str(a.level), '--level', str(a.level_id), '--out', str(out / 'colnames.json')], check=True,
                   capture_output=True)
    names = json.loads((out / 'colnames.json').read_text())
    if a.gate:
        # тот же рой дважды: как есть и с «выключенной картинкой» в круге, покрывающем самый частый видимый ящик;
        # физика одна и та же (прячется только картинка), значит тот же кластер обязан стать «прозрачным»
        seeds = [a.seed0 + k for k in range(a.procs)]
        cl, st = swarm(binary, a.level, a.roads, seeds, 128, 120)
        vis = [c for c in cl.values() if c['kind'] == 'wall' and c['pt'] == 1 and family(c, names) == 'видимая' and c['n'] >= 20]
        if not vis: print('гейт: нет видимого ящика с 20+ ударами'); return 1
        t = max(vis, key=lambda c: c['n'])
        hx, hz, hr = col_box(a.level, t['pi'])
        cl2, _ = swarm(binary, a.level, a.roads, seeds, 128, 120, ('--hide', '%.2f' % hx, '%.2f' % hz, '%.2f' % hr))
        t2 = cl2[('wall', 1, t['pi'])]
        same = t2['n'] == t['n']
        f1, f2 = family(t, names), family(t2, names)
        ok = same and f1 == 'видимая' and f2 in ('прозрачная', 'ступень')
        res = dict(target=src_name(t, names), at=[t['x'], t['y'], t['z']], n=t['n'], before=f1, hidden=f2, sameEvents=same, ok=ok)
        (out / 'gate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"гейт классификатора: {res['target']} ударов {t['n']} -> как есть «{f1}», картинка спрятана «{f2}», события те же {same} -> {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    # рой: длительность подбираем по скорости одного процесса (пробный прогон 20 с)
    if a.seconds is None:
        t0 = time.time(); swarm(binary, a.level, a.roads, [a.seed0 - 1], a.cars, 20); rate = a.cars * 20 / max(time.time() - t0, 1e-3)
        secs = int(max(10, rate * a.minutes * 60 / a.cars * 0.9))
    else:
        secs = a.seconds; rate = 0
        if secs <= 0: raise ValueError('--seconds must be positive')
    seeds = [a.seed0 + k for k in range(a.procs)]
    man = dict(stamp=stamp, level=str(a.level), levelSha=sha(a.level), roadsSha=sha(a.roads), sources={p.name: sha(p) for p in SRC}, binarySha=sha(binary),
               seeds=seeds, cars=a.cars, secs=secs, episode=30, vmin=2.0, command=f'walls --level L --roads R --seed S --cars {a.cars} --secs {secs}')
    (out / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f'рой: {a.procs} процессов × {a.cars} машин × {secs} с (≈{rate:.0f} машино-с/с на процесс), результаты -> {out}', flush=True)
    t0 = time.time(); cl, st = swarm(binary, a.level, a.roads, seeds, a.cars, secs); wall = time.time() - t0
    carSec = sum(s['carSec'] for s in st); km = sum(s['km'] for s in st)
    rows = []
    for c in cl.values():
        c['family'] = family(c, names); c['source'] = src_name(c, names)
        c['origin'] = 'естественное' if c['nNat'] else 'стресс'
        c['key'] = '%s:%d:%d' % (c['kind'], c['pt'], c['pi']) if c['kind'] == 'wall' else '%s@%d,%d,%d' % (c['kind'], c['x'] // 4, c['z'] // 4, c['y'] // 3)
        s_, c_, e_ = (c['seedN'], c['carN'], c['epochN']) if c['nNat'] else (c['seed'], c['car'], c['epoch'])
        c['repro'] = f"{binary} --level {a.level} --roads {a.roads} --seed {s_} --replay {c_} {e_}"
        rows.append(c)
    fam = collections.defaultdict(lambda: [0, 0, 0])   # кластеров, событий естественных, событий стресс
    for c in rows: fam[c['family']][0] += 1; fam[c['family']][1] += c['nNat']; fam[c['family']][2] += c['n'] - c['nNat']
    # приёмка и табло — только естественные события (старт на дороге); стресс отдельно
    tr = [c for c in rows if c['family'] in ('прозрачная', 'дыра')]
    byname = collections.defaultdict(lambda: dict(clusters=0, natural=0, stress=0, examples=[]))
    for c in sorted(tr, key=lambda c: -c['nNat']):
        k = re.sub(r'\d+', '#', c['source']) if c['kind'] == 'wall' else c['kind']
        f = byname[k]; f['clusters'] += 1; f['natural'] += c['nNat']; f['stress'] += c['n'] - c['nNat']
        if len(f['examples']) < 3: f['examples'].append(dict(at=[round(c['x'], 1), round(c['y'], 1), round(c['z'], 1)], natural=c['nNat'], vmax=c['vmax'], repro=c['repro']))
    res = dict(manifest=man, wallSeconds=round(wall, 1), carSeconds=carSec, km=round(km), perSeed=st,
               families={k: dict(clusters=v[0], natural=v[1], stress=v[2]) for k, v in fam.items()},
               transparentByName=dict(sorted(byname.items(), key=lambda kv: -kv[1]['natural'])),
               clusters=sorted(rows, key=lambda c: -c['nNat']))
    (out / 'walls.json').write_text(json.dumps(res, ensure_ascii=False, indent=0))
    top = sorted([c for c in tr if c['nNat']], key=lambda c: -c['nNat'])[:20]
    lines = [f'# Перепись стен {stamp}', '',
             f'Рой: {a.procs}×{a.cars} машин, {carSec / 3600:.0f} машино-часов, {km:.0f} км за {wall / 60:.1f} мин. Уровень {man["levelSha"]}, бинарник {man["binarySha"]}.',
             'Естественное = машина стартовала на дороге (виды 0, 1); стресс = старт на любой опоре или таран (2, 3), в приёмку не входит', '',
             '| семейство | кластеров | событий естественных | стресс |', '|---|---|---|---|'] + [
             f'| {k} | {v[0]} | {v[1]} | {v[2]} |' for k, v in sorted(fam.items(), key=lambda kv: -kv[1][1])] + [
             '', '## Прозрачные и дыры по роду объекта', '', '| род | кластеров | естественных | стресс |', '|---|---|---|---|'] + [
             f"| {k} | {v['clusters']} | {v['natural']} | {v['stress']} |" for k, v in list(res['transparentByName'].items())[:25]] + [
             '', '## Топ-20 по естественным событиям', '', '| # | вид | объект | естеств. | всего | скорость max | где x y z | верх над полом | земля за точкой | повтор |',
             '|---|---|---|---|---|---|---|---|---|---|'] + [
             f"| {i + 1} | {c['family']} | {c['source'] or '-'} | {c['nNat']} | {c['n']} | {c['vmax']:.1f} | {c['x']:.1f} {c['y']:.1f} {c['z']:.1f} | {c['top']:.2f} | {c['rise']:.2f} | `--seed {c['seedN']} --replay {c['carN']} {c['epochN']}` |"
             for i, c in enumerate(top)]
    (out / 'СВОДКА.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:12 + len(fam)]))
    print('\n'.join(lines[-(len(top) + 3):]))
    print('->', out / 'СВОДКА.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
