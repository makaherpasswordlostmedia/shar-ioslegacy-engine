#!/usr/bin/env python3
"""Анатомия уровня 1 по ботам (Роб 04.10: «зачем тест ставит машину в места, где ездить нельзя, в текстуры, в дома? ... одна из
основных задач ботов была понять анатомию уровня: где игра, где тупики, где въехал в текстуры, а оттуда нет выхода»).

  python3 tools/bots/anatomy.py swarm [--procs N] [--secs 90] [--max-min 60] [--out DIR]
      рой исследователей (tools/bots/explorer --cells-out) на ядрах Мака минус 2, без окон и звука, новый seed на каждый
      прогон; раз в минуту — объединённое покрытие (ячейки x, z по 6 м; y по 2 м; режим; опора). Стоп: рост новых ячеек за
      последние 10 мин < 1 % или --max-min минут стены. -> DIR/runs/s<seed>/{cells,edges,events}.tsv, DIR/coverage.tsv
  python3 tools/bots/anatomy.py evidence [--out DIR]
      старые улики застреваний и провалов: build/bots/nights/*/keep, raw, build/bots/runs (stdout.tsv, explore.json,
      chase.json, имена файлов повторов, строка R раундов погони) -> DIR/evidence.tsv
  python3 tools/bots/anatomy.py map --swarm DIR [--evidence F] [--out build/АНАТОМИЯ_L1] [--playable build/playable-l1.tsv]
      карта.png (вид сверху, подложка — город из level.shr, сетка кодов мест L1 K9-7), ЧТО_ГДЕ.txt, playable-l1.tsv

Цвета карты: зелёный — машина ездит по земле (дороги и срезки, связная сеть от спавна); голубой — только пешком; жёлтый — машина
бывает только в воздухе (прыжки) или на острове, куда попадает лишь прыжком (крыши); красный — тупики: машина не выезжает
(проба explorer car_trapped), Гомер заперт (foot_trapped), старые «вечные углы» и застревания погони; фиолетовый — провалы
сквозь землю (fall) и машина на острове под перекрытием (внутри текстур).
playable-l1.tsv — клетки 6 м, где машина ездит по земле в связной сети и goto смоука ставит её именно на эту поверхность
(верхняя опора = поверхность езды), с типичным курсом движения ботов."""
import argparse, collections, json, math, os, re, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / 'build'
REAL = Path('/Users/USER/Downloads/shar-psp')   # данные ботов прошлых ночей (в копии помощника build/ — ссылки)
LV = 1   # уровень (--level N, облако 05.10: полигон L2–L7); set_level переставляет пути данных
LVL, HOM, RDS, ROUTES = B / 'level.shr', B / 'homer.shr', B / 'sandbox/roads-l1.bin', B / 'sandbox/routes-l1.tsv'
TGT = B / 'bots/targets-l1.tsv' if (B / 'bots/targets-l1.tsv').exists() else REAL / 'build/bots/targets-l1.tsv'


def first(*ps):
    for p in ps:
        if p and Path(p).exists(): return Path(p)
    return Path(ps[0])


def set_level(n):
    """данные уровня n (как tools/sandbox/level_check.py: первый существующий путь). L1 — как прежде (build/level.shr, homer.shr).
    L2–L7: build/levels/l<N>/level.shr, игрок уровня l<N>/player.shr (правка 352; нет — homer.shr), дороги ботов
    build/sandbox/roads-l<N>.bin (строит python tools/cartest/roads.py --level N --out …), трамплины routes-l<N>.tsv (нет — рой
    без разгона на трамплины), цели targets-l<N>.tsv (нет — пустой список: исследователь ездит без целей крыш/трамплинов)"""
    global LV, LVL, HOM, RDS, ROUTES, TGT
    LV = n
    if n == 1: return
    L = B / 'levels' / f'l{n}'
    LVL = first(L / 'level.shr')
    HOM = first(L / 'player.shr', B / 'homer.shr')
    RDS = first(B / f'sandbox/roads-l{n}.bin', L / f'roads-l{n}.bin')
    ROUTES = first(B / f'sandbox/routes-l{n}.tsv')
    TGT = first(B / f'bots/targets-l{n}.tsv')


def need_level_data():
    miss = [str(p) for p in (LVL, HOM, RDS) if not p.exists()]
    if miss:
        print(f'anatomy L{LV}: нет данных уровня: ' + ', '.join(miss) +
              (f'\n  дороги: python tools/cartest/roads.py --level {LV} --out build/sandbox/roads-l{LV}.bin' if not RDS.exists() else '') +
              (f'\n  уровень: LEVEL={LV} tools/build_level.sh build/levels/l{LV}/level.shr' if not LVL.exists() else ''), file=sys.stderr)
        sys.exit(2)
X0, Z0, CELL, COLS, ROWS, LETTERS = -700.0, -700.0, 100.0, 12, 15, 'ABCDEFGHJKLM'
G = 6.0   # клетка анатомии, м (как ключ исследователя)


_PLACES = None
def landmark(x, z):
    """ближайшее место оригинала (AddTeleportDest скриптов уровня 1, tools/place.py): «у Kwik E Mart, 40 м»"""
    global _PLACES
    if _PLACES is None:
        try:
            sys.path.insert(0, str(ROOT / 'tools')); import place; _PLACES = place.places(LV)
        except Exception: _PLACES = []
    if not _PLACES: return ''
    nm, px, pz = min(_PLACES, key=lambda p: math.hypot(p[1] - x, p[2] - z)); d = math.hypot(px - x, pz - z)
    return f'у {nm}' if d < 40 else f'{d:.0f} м от {nm}'


def code(x, z):   # viewer/placecode.h
    fx, fz = (x - X0) / CELL, (z - Z0) / CELL
    c, r = math.floor(fx), math.floor(fz)
    if not (0 <= c < COLS and 0 <= r < ROWS): return '--'
    return f'{LETTERS[c]}{r + 1}-{1 + min(2, math.floor((fx - c) * 3)) + 3 * min(2, math.floor((fz - r) * 3))}'


# ------------------------------------------------------------------ рой
def read_cells(p, into, firsts=None):
    """cells.tsv -> into[(x, z, y, режим, опора)] = [посещений, первое, сх, су, сz, верх, ось, сила, курс, скорость] (слияние)"""
    try: txt = p.read_text()
    except OSError: return
    for ln in txt.splitlines():
        if ln.startswith('#'): continue
        f = ln.split('\t')
        if len(f) < 15: continue
        k = (int(f[0]), int(f[1]), int(f[2]), f[3], f[4]); n = int(f[5]); t = float(f[6])
        v = [n, t, float(f[7]) * n, float(f[8]) * n, float(f[9]) * n, float(f[10]), float(f[11]), float(f[12]), float(f[13]), float(f[14])]
        o = into.get(k)
        if o is None: into[k] = v
        else:
            ax0, ax1 = o[6], v[6]; w0, w1 = o[7] * o[0], v[7] * n
            c2 = (w0 * math.cos(2 * ax0) if ax0 == ax0 else 0) + (w1 * math.cos(2 * ax1) if ax1 == ax1 else 0)
            s2 = (w0 * math.sin(2 * ax0) if ax0 == ax0 else 0) + (w1 * math.sin(2 * ax1) if ax1 == ax1 else 0)
            cr = ((o[0] * math.cos(o[8])) if o[8] == o[8] else 0) + ((n * math.cos(v[8])) if v[8] == v[8] else 0)
            sr = ((o[0] * math.sin(o[8])) if o[8] == o[8] else 0) + ((n * math.sin(v[8])) if v[8] == v[8] else 0)
            sp = (o[9] * o[0] + v[9] * n) / (o[0] + n)
            into[k] = [o[0] + n, min(o[1], t), o[2] + v[2], o[3] + v[3], o[4] + v[4], o[5] if o[5] == o[5] else v[5],
                       .5 * math.atan2(s2, c2) if (c2 or s2) else float('nan'), math.hypot(c2, s2) / (o[0] + n) if (c2 or s2) else 0.,
                       math.atan2(sr, cr) if (cr or sr) else float('nan'), sp]


def swarm(a):
    need_level_data()
    out = Path(a.out or B / f'anatomy-l{LV}' / time.strftime('%Y%m%d-%H%M')); (out / 'runs').mkdir(parents=True, exist_ok=True)
    binp = B / 'bots/explorer'
    tgt = TGT
    if not tgt.exists():   # уровень без целей: пустой список (исследователь ездит по дорогам и пешком)
        tgt = out / f'targets-l{LV}-empty.tsv'; tgt.write_text('# нет целей уровня (tools/bots/targets.py — только L1)\n')
    routes = ['--routes', str(ROUTES)] if ROUTES.exists() else []
    procs = a.procs or max(1, (os.cpu_count() or 4) - 2)
    t0 = time.time(); seed = a.seed; jobs = {}; done = set(); union = {}; cached = {}; curve = []
    log = open(out / 'swarm.log', 'a')
    def say(s):
        line = time.strftime('%H:%M:%S') + ' ' + s; print(line, flush=True); log.write(line + '\n'); log.flush()
    say(f'рой: {procs} процессов × {a.secs} с, seed с {seed}, стоп — рост < 1 % за 10 мин или {a.max_min} мин; -> {out}')
    (out / 'args.json').write_text(json.dumps(dict(procs=procs, secs=a.secs, cells=a.cells, seed0=a.seed, max_min=a.max_min, bin=str(binp),
                                                   level=str(LVL), lv=LV, player=str(HOM), roads=str(RDS), targets=str(tgt),
                                                   routes=str(ROUTES) if routes else '-', t0=t0), ensure_ascii=False, indent=1))
    last_cov = 0; stop_why = None
    while True:
        for s, (p, d) in list(jobs.items()):
            if p.poll() is not None: jobs.pop(s); done.add(s)
        el = (time.time() - t0) / 60
        if stop_why is None:
            while len(jobs) < procs:
                d = out / 'runs' / f's{seed}'; d.mkdir(parents=True, exist_ok=True)
                cmd = ['nice', '-n', '10', str(binp), str(LVL), str(HOM), str(RDS), str(tgt), '--secs', str(a.secs), '--seed', str(seed),
                       '--cells', str(a.cells)] + routes + ['--cells-out', str(d)]
                jobs[seed] = (subprocess.Popen(cmd, stdout=open(d / 'stdout.tsv', 'w'), stderr=open(d / 'stderr.txt', 'w'), stdin=subprocess.DEVNULL), d)
                seed += 2   # explorer берёт seed | 1: чётный и следующий нечётный — один и тот же прогон
        if time.time() - last_cov >= 60 or stop_why:
            last_cov = time.time()
            live = {}
            for s in sorted(done):
                if s not in cached: cached[s] = 1; read_cells(out / 'runs' / f's{s}' / 'cells.tsv', union)
            for s, (p, d) in jobs.items(): read_cells(d / 'cells.tsv', live)
            keys = set(union) | set(live)
            firsts = {}
            for k in keys:
                t1 = union[k][1] if k in union else 1e18; t2 = live[k][1] if k in live else 1e18; firsts[k] = min(t1, t2)
            n = len(keys); cg = len({(k[0], k[1]) for k in keys if k[3] == 'car' and k[4] == 'ground'})
            n10 = sum(1 for t in firsts.values() if t <= time.time() - 600)
            g10 = (n - n10) / max(1, n10) * 100 if el >= 10 else float('nan')
            curve.append((round(el, 1), n, cg, len(done), round(g10, 2)))
            (out / 'coverage.tsv').write_text('# минут\tячеек\tклеток_машина_земля\tпрогонов_готово\tрост_за_10мин_%\n' + ''.join('\t'.join(map(str, r)) + '\n' for r in curve))
            say(f'{el:5.1f} мин: ячеек {n}, клеток «машина по земле» {cg}, прогонов {len(done)} готово + {len(jobs)} идут, рост за 10 мин {g10:.2f} %')
            if stop_why: break
            if el >= 10 and g10 < 1.0: stop_why = f'насыщение: рост за 10 мин {g10:.2f} % < 1 %'
            elif el >= a.max_min: stop_why = f'потолок {a.max_min} мин стены'
            if stop_why:
                say('стоп — ' + stop_why + '; идущие прогоны прерываются (у них последняя запись ≤ 30 с назад)')
                for s, (p, d) in jobs.items():
                    try: p.send_signal(signal.SIGTERM)
                    except OSError: pass
                for s, (p, d) in list(jobs.items()): p.wait(); jobs.pop(s); done.add(s)
                continue
        time.sleep(5)
    (out / 'STOP.txt').write_text(stop_why + '\n')
    say(f'итог: {curve[-1]}; -> {out}')


# ------------------------------------------------------------------ старые улики
def evidence(a):
    out = Path(a.out or B / f'anatomy-l{LV}'); out.mkdir(parents=True, exist_ok=True)
    roots = [REAL / 'build/bots/nights', REAL / 'build/bots/runs']
    rows = {}   # (вид, клетка 8 м) -> [x, y, z, раз, источник, последняя дата]
    def add(kind, x, y, z, n, src):
        kind = {'foot_stuck': 'foot_trapped'}.get(kind, kind)
        k = (kind, math.floor(x / 8), math.floor(z / 8)); m = re.search(r'/(20\d{6})-', src); dt = m.group(1) if m else '0'
        if k not in rows: rows[k] = [x, y, z, 0, src, dt]
        rows[k][3] += n; rows[k][5] = max(rows[k][5], dt)
    nfiles = 0
    for r in roots:
        for p in r.rglob('stdout.tsv'):
            if 'gate' in str(p) or 'planted' in str(p) or 'broken' in str(p): continue   # гейты: подложенные углы и сломанные сборки
            for ln in p.read_text(errors='replace').splitlines():
                f = ln.split('\t')
                try:
                    if f[0] == 'E' and len(f) >= 6: add(f[1], float(f[2]), float(f[3]), float(f[4]), int(f[5]), str(p.relative_to(REAL)))
                    elif f[0] == 'X' and len(f) >= 6: add(f[1], float(f[2]), float(f[3]), float(f[4]), int(f[5]), str(p.relative_to(REAL)))
                except ValueError: pass
            nfiles += 1
        for p in r.rglob('*'):
            if not p.is_file() or 'gate' in str(p) or 'planted' in str(p) or 'broken' in str(p): continue
            nm = p.name
            if nm.endswith('.round'):   # строка R: выжил пойман угол застряла kx ky kz sx sy sz
                m = re.search(r'(eternal_corner|pursuer_stuck)', nm)
                if not m: continue
                try:
                    for ln in p.read_text(errors='replace').splitlines():
                        if ln.startswith('R '):
                            v = ln.split(); corner, stuck = int(v[3]), int(v[4]); kx, ky, kz, sx, sy, sz = map(float, v[5:11])
                            if m.group(1) == 'eternal_corner' and corner: add('eternal_corner', kx, ky, kz, 1, str(p.relative_to(REAL)))
                            if m.group(1) == 'pursuer_stuck' and stuck: add('pursuer_stuck', sx, sy, sz, 1, str(p.relative_to(REAL)))
                except (ValueError, IndexError): pass
                nfiles += 1
            elif nm.startswith('ev_') and nm.endswith('.in'):   # ev_<вид>_<x>_<z>[_L<слой>_<объект>].in: клетка 8 м
                m = re.match(r'ev_(foot_trapped|foot_stuck|fall|car_trapped)_(-?\d+)_(-?\d+)', nm)
                if m: add(m.group(1), float(m.group(2)) + 4, float('nan'), float(m.group(3)) + 4, 1, str(p.relative_to(REAL))); nfiles += 1
    L = ['# вид\tx\ty\tz\tраз\tисточник (первый)\tпоследняя дата']
    for (kind, gx, gz), v in sorted(rows.items()):
        L.append(f'{kind}\t{v[0]:.1f}\t{v[1]:.1f}\t{v[2]:.1f}\t{v[3]}\t{v[4]}\t{v[5]}')
    (out / 'evidence.tsv').write_text('\n'.join(L) + '\n')
    c = collections.Counter(k[0] for k in rows)
    print(f'улик прочитано файлов {nfiles}; мест (вид + клетка 8 м): ' + ', '.join(f'{k} {n}' for k, n in sorted(c.items())) + f' -> {out / "evidence.tsv"}')


# ------------------------------------------------------------------ карта
def load_swarm(d):
    cells = {}; edges = collections.Counter(); events = []
    for r in sorted((Path(d) / 'runs').glob('s*')):
        read_cells(r / 'cells.tsv', cells)
        try:
            for ln in (r / 'edges.tsv').read_text().splitlines():
                if ln.startswith('#'): continue
                f = ln.split('\t'); edges[(int(f[0]), int(f[1]), int(f[2]), int(f[3]), int(f[4]), int(f[5]))] += int(f[6])
        except OSError: pass
        try:
            for ln in (r / 'events.tsv').read_text().splitlines():
                if ln.startswith('#'): continue
                f = ln.split('\t'); events.append(dict(kind=f[0], x=float(f[1]), y=float(f[2]), z=float(f[3]), t=float(f[4]), layer=int(f[5]), obj=f[6], foot=int(f[7]), run=r.name))
        except OSError: pass
    return cells, edges, events


def analyse(cells, edges):
    """-> по клетке 6 м (x, z): класс и данные. Связная сеть машины по земле — компонента переходов edges, где спавн."""
    cg = {}   # (x, z, y) -> запись: машина на земле
    for k, v in cells.items():
        if k[3] == 'car' and k[4] == 'ground': cg[(k[0], k[1], k[2])] = v
    adj = collections.defaultdict(set)
    for (xa, za, ya, xb, zb, yb), n in edges.items():
        a, b = (xa, za, ya), (xb, zb, yb)
        if a in cg and b in cg: adj[a].add(b); adj[b].add(a)
    # и соседство: клетки 6 м рядом (8 соседей), средние высоты езды ближе 0.8 м — одна поверхность (бот просто не проехал
    # между ними в этом прогоне); крыша, навес, эстакада выше на метры — не соседи
    for (x, z, y), v in cg.items():
        my = v[3] / v[0]
        for dx in (-6, 0, 6):
            for dz in (-6, 0, 6):
                if not dx and not dz: continue
                for dy in (-2, 0, 2):
                    w = cg.get((x + dx, z + dz, y + dy))
                    if w and abs(w[3] / w[0] - my) <= .8: adj[(x, z, y)].add((x + dx, z + dz, y + dy))
    comp = {}; sizes = []
    for s in cg:
        if s in comp: continue
        cid = len(sizes); stack = [s]; comp[s] = cid; n = 0
        while stack:
            u = stack.pop(); n += 1
            for w in adj[u]:
                if w not in comp: comp[w] = cid; stack.append(w)
        sizes.append(n)
    # спавн уровня 1 (220, 172) — компонента с ним; иначе самая большая
    sp = [k for k in cg if abs(k[0] + 3 - 220) < 9 and abs(k[1] + 3 - 172) < 9]
    main = collections.Counter(comp[k] for k in sp).most_common(1)[0][0] if sp else max(range(len(sizes)), key=lambda i: sizes[i])
    col = collections.defaultdict(lambda: dict(car_ground=0, car_main=0, car_air=0, foot=0, island=0, island_cover=0, y=[], top=[], ax=[], hits=0))
    for k, v in cells.items():
        c = col[(k[0], k[1])]; c['hits'] += v[0]
        if k[3] == 'car' and k[4] == 'ground':
            key3 = (k[0], k[1], k[2]); my = v[3] / v[0]
            if comp[key3] == main:
                c['car_main'] += v[0]; c['y'].append((v[0], my, v[5], v[6], v[7], v[2] / v[0], v[4] / v[0]))
            else:
                c['island'] += v[0]
                if v[5] == v[5] and v[5] - my > 3.0: c['island_cover'] += v[0]   # над машиной перекрытие (верхняя опора выше на 3 м)
            c['car_ground'] += v[0]
        elif k[3] == 'car': c['car_air'] += v[0]
        else: c['foot'] += v[0]
    return col, sizes, main


def classify(c):
    if c['car_main']: return 'green'
    if c['island_cover'] and c['island_cover'] >= c['island'] * .5: return 'violet_in'
    if c['island'] or c['car_air']: return 'yellow'
    if c['foot']: return 'blue'
    return None


def playable_rows(col):
    """клетки зелёной сети, где goto ставит машину на поверхность езды: верхняя опора над средней точкой ≈ её высоте (±1.5 м)"""
    rows = []
    for (x, z), c in col.items():
        if not c['car_main']: continue
        n, my, top, ax, st, mx, mz = max(c['y'], key=lambda r: r[0])   # самый частый этаж езды
        ontop = top == top and abs(top - my) < 1.5
        rows.append((x, z, my, top, ax, st, c['car_main'], int(ontop), mx, mz))
    return rows


def sub_masks(rows):
    """маска клетки 6 м: 9 точек через 2 м (x + 1 + 2i, z + 1 + 2j; i — быстрый индекс): '1' — goto кладёт машину на высоту езды
    ботов (± 1.5 м), '0' — на крышу, навес, ящик над ней или опоры нет. Считает tools/bots/tops (тот же код коллизии)"""
    binp = B / 'bots/tops'
    if not binp.exists(): subprocess.run([str(ROOT / 'tools/bots/build.sh')], env=dict(os.environ, BINS='tops'), check=True, capture_output=True)
    pts = [(x + 1 + 2 * i, z + 1 + 2 * j) for x, z, *_ in rows for j in range(3) for i in range(3)]
    r = subprocess.run([str(binp), str(LVL), str(HOM)], input=''.join(f'{a} {b}\n' for a, b in pts), capture_output=True, text=True, check=True)
    tops = [float(l.split()[2]) for l in r.stdout.splitlines()]
    out = []
    for k, (x, z, my, *_) in enumerate(rows):
        t = tops[9 * k: 9 * k + 9]; out.append(''.join('1' if v == v and abs(v - my) < 1.5 else '0' for v in t))
    return out


def road_flags(rows):
    """на дороге из данных уровня (build/sandbox/roads-l1.bin: отрезки дорог с полушириной): средняя точка клетки ближе полуширины + 1 м
    к отрезку и по высоте ± 2.5 м -> 1. Точки тура сдвигаются в первую очередь на такие клетки (асфальт, не газон рядом)"""
    import numpy as np
    try: R = np.fromfile(RDS, dtype=np.float32).reshape(-1, 7)
    except (OSError, ValueError): return [0] * len(rows)
    A, Bv, hw = R[:, [0, 2]], R[:, [3, 5]], R[:, 6]; ya, yb = R[:, 1], R[:, 4]
    out = []
    for x, z, my, top, ax, st, n, ok, mx, mz in rows:
        p = np.array([mx, mz]); d = Bv - A; L2 = (d * d).sum(1) + 1e-9; t = np.clip(((p - A) * d).sum(1) / L2, 0, 1)
        q = A + d * t[:, None]; dist = np.hypot(*(p - q).T); yy = ya + (yb - ya) * t
        out.append(int(bool(((dist <= hw + 1.) & (np.abs(yy - my) < 2.5)).any())))
    return out


def course_txt(ax):
    if ax != ax: return '-'
    return f'{ax:.3f}'


RECENT = '20261002'   # провалы сквозь землю почти исчезли с ночи 02.10 (было 3–5 тыс. повторов за ночь, стало < 100): старше — прежняя физика
BUSY = 100            # выборок «машина по земле» в клетке 6 м: тут сегодня ездят свободно
def judge_evidence(evid, col, events):
    """старая улика -> e['shown'], e['why']. На карту — только то, что сегодняшний рой не опроверг: провалы и запертый Гомер — с ночи
    02.10 (раньше — прежняя физика); застревание погони — где повторялось ≥ 3 раз (одиночные — промахи водителя погони); и любая
    старая улика не рисуется, если в её клетке сегодня машина свободно ездит (≥ BUSY выборок) и свежий рой рядом (12 м) такого не нашёл"""
    fresh = collections.defaultdict(list)
    for e in events: fresh['fall' if e['kind'] == 'fall' else 'red'].append((e['x'], e['z']))
    for e in evid:
        grp = 'fall' if e['kind'] == 'fall' else 'red'
        if e['x'] != e['x']: e['shown'], e['why'] = False, 'нет координат'; continue
        if e['kind'] in ('fall', 'foot_trapped') and e['date'] < RECENT: e['shown'], e['why'] = False, 'прежняя физика (до 02.10)'; continue
        if e['kind'] == 'pursuer_stuck' and e['n'] < 3: e['shown'], e['why'] = False, 'одиночное застревание погони'; continue
        c = col.get((int(math.floor(e['x'] / G) * G), int(math.floor(e['z'] / G) * G)))
        near = any(math.hypot(e['x'] - x, e['z'] - z) < 12 for x, z in fresh[grp])
        if c and c['car_main'] >= BUSY and not near: e['shown'], e['why'] = False, 'сегодня тут свободно ездят'; continue
        e['shown'], e['why'] = True, 'подтверждено свежим роем рядом' if near else 'не опровергнуто'
def shown_evidence(e): return e.get('shown', True)


def render(col, events, evid, out, title_extra, roadset=frozenset()):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    sys.path.insert(0, str(ROOT / 'tools'))
    xs = [k[0] for k in col]; zs = [k[1] for k in col]
    xa, xb = max(0, math.floor((min(xs) - 40 - X0) / CELL)), min(COLS, math.ceil((max(xs) + 46 - X0) / CELL))
    za, zb = max(0, math.floor((min(zs) - 40 - Z0) / CELL)), min(ROWS, math.ceil((max(zs) + 46 - Z0) / CELL))
    PX, PAD, LEG = 2.0, 60, 520
    W, H = int((xb - xa) * CELL * PX) + 2 * PAD + LEG, int((zb - za) * CELL * PX) + 2 * PAD
    ex = lambda x: PAD + (x - (X0 + xa * CELL)) * PX
    ez = lambda z: PAD + (z - (Z0 + za * CELL)) * PX
    img = Image.new('RGB', (W, H), (246, 245, 240)); dr = ImageDraw.Draw(img)
    # подложка: город уровня сверху (level.shr) — треугольники средним цветом текстуры, бледно, снизу вверх (как tools/place.py --sheet)
    try:
        import place, shr7read
        L = shr7read.load(LVL); means = place.tex_means(LVL.read_bytes()); P = L['P']; keep = (L['FL'] & 4) == 0
        order = np.argsort(P[:, :, 1].max(1))
        # высота над местной землёй: минимум высот вершин в клетке 16 м и её соседях — крыша над улицей темнее, холм — нет
        cx = np.floor((P[:, :, 0].mean(1) - X0) / 16).astype(int); cz = np.floor((P[:, :, 2].mean(1) - Z0) / 16).astype(int)
        gmin = np.full((cx.max() + 3, cz.max() + 3), 1e9); np.minimum.at(gmin, (cx + 1, cz + 1), P[:, :, 1].min(1))
        lmin = gmin.copy()
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1): lmin = np.minimum(lmin, np.roll(np.roll(gmin, dx, 0), dz, 1))
        rel = P[:, :, 1].max(1) - lmin[cx + 1, cz + 1]
        span = np.max([np.hypot(*(P[:, a, ::2] - P[:, b, ::2]).T) for a, b in ((0, 1), (1, 2), (2, 0))], 0)
        rel = np.where(span < 25., rel, rel * .2)   # большие треугольники — склоны холмов вокруг города, не дома: почти не темнить
        def tone(c, h):   # цвет текстуры приглушён (насыщенность 35 %, бледнее), выше местной земли — темнее: дома и кроны читаются
            g = .3 * c[0] + .59 * c[1] + .11 * c[2]; dk = min(.35, max(0., (h - 1.5) / 14.))
            return tuple(int(((g + (c[k] - g) * .35) * .5 + 246 * .5) * (1 - dk)) for k in range(3))
        for i in order:
            if not keep[i] or L['TEX'][i] < 0: continue
            q = P[i]; dr.polygon([(ex(q[k, 0]), ez(q[k, 2])) for k in range(3)], fill=tone(means[L['TEX'][i]], rel[i]))
        under = 'город из level.shr сверху (выше — темнее)'
    except Exception as e:   # без подложки карта всё равно читается по клеткам
        under = f'без подложки ({e})'
    over = Image.new('RGBA', (W, H), (0, 0, 0, 0)); do = ImageDraw.Draw(over)
    COL = dict(green=(120, 215, 110, 120), road=(10, 150, 45, 175), blue=(30, 150, 240, 125), yellow=(250, 205, 0, 170), violet_in=(150, 40, 200, 200))
    cnt = collections.Counter()
    for (x, z), c in col.items():
        k = classify(c)
        if not k: continue
        cnt[k] += 1
        if k == 'green' and (x, z) in roadset: k = 'road'; cnt['road'] += 1
        do.rectangle([ex(x), ez(z), ex(x + G) - 1, ez(z + G) - 1], fill=COL[k])
    img = Image.alpha_composite(img.convert('RGBA'), over).convert('RGB'); dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 26)
        small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
        leg = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 19)
        legb = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 22)
    except OSError:
        font = small = leg = legb = ImageFont.load_default()
    # сетка кодов мест: квадраты 100 м (буква столбца, номер ряда), участки 33 м — тонко
    for c in range(xa, xb + 1):
        X = ex(X0 + c * CELL); dr.line([X, PAD, X, H - PAD], fill=(200, 60, 40), width=2)
        if c < xb:
            for k in (1, 2): xx = ex(X0 + (c + k / 3) * CELL); dr.line([xx, PAD, xx, H - PAD], fill=(225, 175, 165), width=1)
            dr.text((ex(X0 + (c + .5) * CELL) - 8, 18), LETTERS[c], fill=(200, 60, 40), font=font)
            dr.text((ex(X0 + (c + .5) * CELL) - 8, H - PAD + 14), LETTERS[c], fill=(200, 60, 40), font=font)
    for r in range(za, zb + 1):
        Z = ez(Z0 + r * CELL); dr.line([PAD, Z, ex(X0 + xb * CELL), Z], fill=(200, 60, 40), width=2)
        if r < zb:
            for k in (1, 2): zz = ez(Z0 + (r + k / 3) * CELL); dr.line([PAD, zz, ex(X0 + xb * CELL), zz], fill=(225, 175, 165), width=1)
            dr.text((12, ez(Z0 + (r + .5) * CELL) - 14), str(r + 1), fill=(200, 60, 40), font=font)
            dr.text((ex(X0 + xb * CELL) + 10, ez(Z0 + (r + .5) * CELL) - 14), str(r + 1), fill=(200, 60, 40), font=font)
    # участки 1…9 мелко в углу каждого квадрата 33 м
    for c in range(xa, xb):
        for r in range(za, zb):
            for s in range(9):
                sx, sz = s % 3, s // 3
                dr.text((ex(X0 + (c + sx / 3) * CELL) + 3, ez(Z0 + (r + sz / 3) * CELL) + 2), str(s + 1), fill=(205, 120, 110), font=small)
    # события: красный — тупики, фиолетовый — провалы; крупный — свежий рой, кольцо — старые улики ночей
    def dot(x, z, rgb, rad, ring=False):
        if ring: dr.ellipse([ex(x) - rad, ez(z) - rad, ex(x) + rad, ez(z) + rad], outline=rgb, width=3)
        else: dr.ellipse([ex(x) - rad, ez(z) - rad, ex(x) + rad, ez(z) + rad], fill=rgb, outline=(255, 255, 255), width=1)
    RED, VIO = (220, 20, 30), (120, 0, 170)
    for e in evid:
        if e['x'] != e['x'] or not shown_evidence(e): continue
        dot(e['x'], e['z'], VIO if e['kind'] == 'fall' else RED, 6, ring=True)
    for e in events:
        dot(e['x'], e['z'], VIO if e['kind'] == 'fall' else RED, 5)
    # легенда
    lx = W - LEG + 20; y = PAD
    dr.text((lx, y), 'Анатомия уровня 1 по ботам', fill=(20, 20, 20), font=legb); y += 34
    for ln in title_extra: dr.text((lx, y), ln, fill=(60, 60, 60), font=small); y += 20
    y += 12
    items = [((10, 150, 45), 'машина ездит по дороге', 'дороги из данных уровня; связная сеть от спавна'),
             ((120, 215, 110), 'машина ездит по срезкам', 'газоны, дворы, тропы, парковки — та же сеть'),
             ((40, 160, 230), 'только пешком', 'машина сюда не попадала'),
             ((245, 200, 0), 'машина только в прыжке', 'или на крыше, куда попадает лишь прыжком'),
             ((220, 20, 30), 'тупик: машина не выезжает,', 'Гомер заперт, погоня застряла'),
             ((150, 40, 200), 'провал сквозь землю', 'или машина внутри текстур (под перекрытием)')]
    for rgb, a1, a2 in items:
        dr.rectangle([lx, y + 2, lx + 30, y + 30], fill=rgb); dr.text((lx + 42, y), a1, fill=(20, 20, 20), font=leg); dr.text((lx + 42, y + 22), a2, fill=(90, 90, 90), font=small); y += 54
    y += 6
    dr.ellipse([lx + 8, y + 4, lx + 22, y + 18], fill=RED, outline=(255, 255, 255)); dr.text((lx + 42, y), 'точка — событие свежего роя (сегодня)', fill=(20, 20, 20), font=small); y += 26
    dr.ellipse([lx + 8, y + 4, lx + 22, y + 18], outline=RED, width=3); dr.text((lx + 42, y), 'кольцо — старая улика прошлых ночей', fill=(20, 20, 20), font=small); y += 34
    dr.text((lx, y), f'Сетка — коды мест, как в игре: L{LV} K9-7 =', fill=(20, 20, 20), font=small); y += 20
    dr.text((lx, y), 'буква столбца, номер ряда (квадрат 100 м),', fill=(20, 20, 20), font=small); y += 20
    dr.text((lx, y), 'цифра участка 33 м — как на кнопках телефона', fill=(20, 20, 20), font=small); y += 26
    dr.text((lx, y), f'Подложка: {under}', fill=(90, 90, 90), font=small); y += 20
    dr.text((lx, y), f'Клетка цвета — 6 × 6 м', fill=(90, 90, 90), font=small); y += 30
    for k, nm in (('green', 'зелёных (из них дорога ' + str(cnt['road']) + ')'), ('blue', 'голубых'), ('yellow', 'жёлтых'), ('violet_in', 'фиолетовых (внутри)')):
        dr.text((lx, y), f'клеток {nm}: {cnt[k]}', fill=(40, 40, 40), font=small); y += 20
    out.mkdir(parents=True, exist_ok=True); img.save(out / 'карта.png', optimize=True)
    return cnt


def mapcmd(a):
    need_level_data()
    sw = Path(a.swarm); out = Path(a.out or B / f'АНАТОМИЯ_L{LV}'); out.mkdir(parents=True, exist_ok=True)
    cells, edges, events = load_swarm(sw)
    col, sizes, main = analyse(cells, edges)
    evid = []
    if a.evidence and Path(a.evidence).exists():
        for ln in Path(a.evidence).read_text().splitlines():
            if ln.startswith('#'): continue
            f = ln.split('\t'); evid.append(dict(kind=f[0], x=float(f[1]), y=float(f[2]), z=float(f[3]), n=int(f[4]), src=f[5], date=f[6] if len(f) > 6 else '0'))
    cov = [l.split('\t') for l in (sw / 'coverage.tsv').read_text().splitlines()[1:]] if (sw / 'coverage.tsv').exists() else []
    args = json.loads((sw / 'args.json').read_text()) if (sw / 'args.json').exists() else {}
    stop = (sw / 'STOP.txt').read_text().strip() if (sw / 'STOP.txt').exists() else '?'
    nruns = len(list((sw / 'runs').glob('s*')))
    title = [f'рой {args.get("procs", "?")} процессов, прогонов {nruns}, {cov[-1][0] if cov else "?"} мин стены',
             f'стоп: {stop}', f'ячеек всего {len(cells)}; уровень level.shr']
    judge_evidence(evid, col, events)
    rows = playable_rows(col)
    roads = road_flags(sorted(rows))
    roadset = frozenset((r[0], r[1]) for r, f in zip(sorted(rows), roads) if f)
    cnt = render(col, events, evid, out, title, roadset)
    pl = Path(a.playable or B / f'playable-l{LV}.tsv')
    L = ['# Проезжие клетки уровня 1 по ботам (tools/bots/anatomy.py map): машина ездит здесь по земле, клетка в связной сети от спавна.',
         f'# Рой: {sw}; клетка 6 м: x, z — угол клетки (движок, как goto смоука); y — высота езды; верх_y — верхняя опора (куда ставит goto);',
         '# goto_ok = 1: goto ставит машину на эту поверхность (верх ≈ y ± 1.5 м); курс_ось — типичный курс движения ботов (рад, по модулю π,',
         '# вперёд = (sin h, cos h), как у goto); сила_оси 0..1 — насколько движение вдоль одной оси; выборок — сколько раз бот тут был',
         '# ср_x, ср_z — средняя точка проездов ботов в клетке (туда сдвигает точки тура tools/tour_playable.py); маска — 9 точек клетки через 2 м',
         '# (x + 1 + 2i, z + 1 + 2j, i быстрый): 1 — goto кладёт машину на высоту езды, 0 — на крышу, навес, ящик над ней (tools/bots/tops)',
         f'# дорога = 1: средняя точка на отрезке дороги из данных уровня (roads-l{LV}.bin), не на газоне или тротуаре рядом',
         '# x\tz\ty\tверх_y\tкурс_ось\tсила_оси\tвыборок\tgoto_ok\tкод\tср_x\tср_z\tмаска\tдорога']
    rows = sorted(rows); masks = sub_masks(rows); roads = road_flags(rows)
    for (x, z, my, top, ax, st, n, ok, mx, mz), m, rd in zip(rows, masks, roads):
        L.append(f'{x}\t{z}\t{my:.2f}\t{top:.2f}\t{course_txt(ax)}\t{st:.2f}\t{n}\t{ok}\t{code(x + 3, z + 3)}\t{mx:.2f}\t{mz:.2f}\t{m}\t{rd}')
    pl.write_text('\n'.join(L) + '\n')
    # ЧТО_ГДЕ.txt
    byk = collections.defaultdict(list)
    for e in events: byk[e['kind']].append(e)
    def clusters(es, r=8.0):
        cl = {}
        for e in es:
            k = (math.floor(e['x'] / r), math.floor(e['z'] / r))
            if k not in cl: cl[k] = [e, 0]
            cl[k][1] += 1
        return sorted(cl.values(), key=lambda v: -v[1])
    nm = dict(car_trapped='машина не выезжает (встала в узком месте: ни вперёд, ни назад, ни с рулём за 2.5 с)', foot_trapped='Гомер заперт', fall='провал сквозь землю / за край',
              eternal_corner='вечный угол погони', pursuer_stuck='погоня застряла')
    green = cnt['green']; area = lambda n: n * G * G / 1e4
    T = [f'АНАТОМИЯ УРОВНЯ 1 ПО БОТАМ — {time.strftime("%d.%m.%Y %H:%M")}', '',
         'Откуда: рой исследователей (tools/bots/explorer --cells-out) на процессоре Мака: тот же код игры, что на PSP, без экрана.',
         f'Старты: спавн, точки дорог, начала разгонов к трамплинам. {title[0]}; {title[1]}.', '',
         'ЦВЕТА НА КАРТЕ (карта.png)',
         f'  зелёный — машина ездит по земле (одна связная сеть от спавна): клеток {green} (~{area(green):.1f} га); тёмно-зелёный — дорога',
         f'    из данных уровня ({cnt["road"]} клеток), светло-зелёный — срезки: газоны, дворы, тропы, парковки ({green - cnt["road"]})',
         f'  голубой — только пешком: клеток {cnt["blue"]}',
         f'  жёлтый — машина бывает только в прыжке или на крыше, куда попадает лишь прыжком: клеток {cnt["yellow"]}',
         f'  фиолетовый (клетки) — машина на острове под перекрытием (внутри текстур): клеток {cnt["violet_in"]}',
         f'  красные точки — тупики свежего роя; фиолетовые точки — провалы; кольца — старые улики прошлых ночей', '',
         f'Связная сеть машины: {sizes[main] if sizes else 0} ячеек; отдельных островов «машина по земле» без въезда по земле: {len(sizes) - 1}', '']
    isl = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
    for (x, z), c in col.items():
        k = classify(c)
        if k in ('yellow', 'violet_in'):
            q = code(x + 3, z + 3).split('-')[0]; r = isl[(k, q)]; r[0] += 1; r[1] += c['island'] + c['car_air']; r[2] += x + 3; r[3] += z + 3
    if isl:
        T.append('КУДА МАШИНА ПОПАДАЕТ ТОЛЬКО ПРЫЖКОМ (жёлтое) И ГДЕ ОНА ВНУТРИ ТЕКСТУР (фиолетовые клетки) — по квадратам 100 м')
        for (k, q), r in sorted(isl.items(), key=lambda kv: -kv[1][0]):
            if r[0] < 4: continue
            T.append(f'  L{LV} {q}: {"внутри текстур / под перекрытием" if k == "violet_in" else "только прыжком"} — клеток {r[0]}, выборок машины {r[1]}  ({landmark(r[2] / r[0], r[3] / r[0])})')
        T.append('')
    if cov:
        T += ['ПОКРЫТИЕ ПО ВРЕМЕНИ (рой: минут стены -> ячеек всего / клеток «машина по земле», рост за последние 10 мин)']
        for r in cov:
            if float(r[0]) % 5 < 1.01 or r is cov[-1]: T.append(f'  {float(r[0]):5.1f} мин: {r[1]} / {r[2]}' + (f', рост {r[4]} %' if r[4] != 'nan' else ''))
        T.append('')
    for kind in ('car_trapped', 'foot_trapped', 'fall'):
        cl = clusters(byk.get(kind, []))
        T.append(f'{nm[kind].upper()} — свежий рой: мест (клетка 8 м) {len(cl)}, случаев {len(byk.get(kind, []))}')
        for e, n in cl[:25]:
            T.append(f'  L{LV} {code(e["x"], e["z"])}  x {e["x"]:.0f} z {e["z"]:.0f} y {e["y"]:.1f}  раз {n}  {landmark(e["x"], e["z"])}' + (f'  объект {e["obj"]}' if e['obj'] != '-' else ''))
        if len(cl) > 25: T.append(f'  … ещё {len(cl) - 25}')
        T.append('')
    if evid:
        ek = collections.defaultdict(list)
        for e in evid: ek[e['kind']].append(e)
        T.append('СТАРЫЕ УЛИКИ (build/bots/nights/*/keep, raw и build/bots/runs; прежние версии кода и данных) — кольца на карте только там,')
        T.append('  где сегодняшний рой их не опроверг (правило: tools/bots/anatomy.py judge_evidence)')
        for kind, es in sorted(ek.items()):
            es.sort(key=lambda e: -e['n']); sh = [e for e in es if e.get('shown')]
            why = collections.Counter(e['why'] for e in es if not e.get('shown'))
            T.append(f'  {nm.get(kind, kind)}: мест {len(es)}, случаев {sum(e["n"] for e in es)}; на карте {len(sh)}' +
                     (' (не на карте: ' + ', '.join(f'{w} {n}' for w, n in why.most_common()) + ')' if why else ''))
            for e in sh[:10]: T.append(f'    L{LV} {code(e["x"], e["z"])}  x {e["x"]:.0f} z {e["z"]:.0f}  раз {e["n"]}  {landmark(e["x"], e["z"])}; {e["why"]}')
        T.append('')
    T += ['ЧТО ЭТО ЗНАЧИТ ДЛЯ ТЕСТА', '  Замер-тур (tools/tour_make.py) ставит машину только в зелёные клетки, где goto кладёт её на ту же поверхность,',
          f'  по которой ездят боты, курсом вдоль их движения (build/playable-l{LV}.tsv). Точка вне зелёного — сдвиг на ближайшую или выброс.',
          '', 'ЧЕГО КАРТА НЕ ЗНАЕТ', '  Комнаты (интерьеры) — не город, на карте их нет. Миссии и машины миссий в рое не участвуют.',
          '  Голубое и жёлтое — то, что бот нашёл за прогон; пусто — не значит недостижимо, значит не найдено.']
    (out / 'ЧТО_ГДЕ.txt').write_text('\n'.join(T) + '\n')
    print(f'карта -> {out / "карта.png"}; описание -> {out / "ЧТО_ГДЕ.txt"}; проезжие клетки {len(rows)} (goto_ok {sum(r[7] for r in rows)}) -> {pl}')
    print('  ' + ', '.join(f'{k} {v}' for k, v in cnt.items()) + f'; событий роя: ' + ', '.join(f'{k} {len(v)}' for k, v in byk.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('swarm'); s.add_argument('--procs', type=int, default=0); s.add_argument('--secs', type=float, default=90)
    s.add_argument('--cells', type=int, default=6000); s.add_argument('--seed', type=int, default=1001); s.add_argument('--max-min', type=float, default=60)
    s.add_argument('--out')
    e = sp.add_parser('evidence'); e.add_argument('--out')
    m = sp.add_parser('map'); m.add_argument('--swarm', required=True); m.add_argument('--evidence'); m.add_argument('--out'); m.add_argument('--playable')
    for x in (s, e, m): x.add_argument('--level', type=int, default=1, choices=range(1, 8))   # облако 05.10: полигон L2–L7
    a = ap.parse_args()
    set_level(a.level)
    {'swarm': swarm, 'evidence': evidence, 'map': mapcmd}[a.cmd](a)


if __name__ == '__main__':
    main()
