#!/usr/bin/env python3
"""П2.1 · провалы под мир: топ мест `fall` ночи ботов → точка, курс и скорость до провала → вопрос оригиналу (ask.py).
  python3 tools/ps2ref/falls.py top [--night DIR] [--n 20]   места (как утро: tools/bots/night.py regions, без known.tsv),
        повтор каждого .in замороженным game_headless ночи (GH_TRACE=1) → build/ps2ref/falls/top.json и top.tsv
Координаты: порт (level.shr, z отражён); оригинал = (x, y, −z). Курс в порту — atan2(vx, vz); в оригинале vz меняет знак.
Кода игры не касаемся: бот — наш мир, оригинал — только ask.py (запись в проверенные car_cm / car_vel)."""
import json, math, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/bots')); sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'build/ps2ref/falls'
TR = re.compile(r'кадр (\d+) (\S+) (\S+) (\S+) (\S+) на земле (\d) vy (\S+) ввод (\S+) (\S+) (\S+) состояние (\d+)')


def last_night():
    ns = sorted(p.parent for p in (ROOT / 'build/bots/nights').glob('*/night.json') if re.fullmatch(r'\d{8}-\d{4}', p.parent.name))
    return ns[-1]


def deaths_port():
    """зоны DEATH оригинала (Event 4) в координатах порта: все объёмы каждого локатора"""
    import jumps_export as J
    from p3dlocs import read_locators
    out, seen = [], set()
    for f in J.script_files(1) + [p for p in J.scene_files(1) if p.exists()]:
        locs, err = read_locators(f, str(f.relative_to(J.GAME)))
        if err: continue
        for L in locs:
            if L.type != 0 or L.data != J.EV_DEATH or not L.triggers: continue
            key = (L.name, round(L.pos[0], 2), round(L.pos[2], 2))
            if key in seen: continue
            seen.add(key)
            for rect, c, h, axes in L.triggers:
                if not rect: axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)); h = (h[0], h[0], h[0])
                out.append(dict(name=L.name, c=c, axes=axes, h=h, apex=L.pos))
    return out


def in_death(D, x, y, z, grow=0.0):
    for d in D:
        q = (x - d['c'][0], y - d['c'][1], z - d['c'][2])
        if all(abs(sum(q[i] * d['axes'][k][i] for i in range(3))) <= d['h'][k] + grow for k in range(3)): return d['name']
    return None


def replay(N, repro):
    """повтор .in замороженным game_headless ночи → [(кадр, пешком, x, y, z, на земле, vy)]"""
    head = Path(ROOT / repro).read_text().splitlines()[0]
    m = re.search(r'--start (\S+) (\S+) (\S+) (\S+)', head)
    cmd = [str(N / 'bin/game_headless'), str(N / 'in/build/level.shr'), str(N / 'in/build/homer.shr'), '--input', str(ROOT / repro)]
    if m: cmd += ['--start', *m.groups()]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, GH_TRACE='1'), timeout=120)
    rows = []
    for l in r.stderr.splitlines():
        t = TR.match(l)
        if t: rows.append((int(t[1]), t[2] == 'Гомер', float(t[3]), float(t[4]), float(t[5]), int(t[6]), float(t[7])))
    return rows, head


def depart(rows, D=None):
    """откуда упал: последний кадр на законной опоре (y > −5 м, не в объёме зоны DEATH оригинала) перед концом повтора;
    край — следующий кадр; скорость и курс — по разности позиций за 6 кадров до ухода (мир ботов 60 кадров/с).
    Дно оврага внутри зоны DEATH законной опорой не считается: в оригинале игрока оттуда возвращает зона"""
    n = len(rows)
    legit = [k for k in range(n - 1) if rows[k][5] and rows[k][3] > -5 and not (D and in_death(D, rows[k][2], rows[k][3] + 0.5, rows[k][4]))]
    k = legit[-1] if legit else 0
    b = rows[k]; e = rows[min(k + 1, n - 1)]; p = rows[max(0, k - 6)]; dt = (b[0] - p[0]) / 60.0 or 1 / 60
    vx, vz = (b[2] - p[2]) / dt, (b[4] - p[4]) / dt
    lands = []
    for r in rows[k + 1:]:
        if r[5] and (not lands or abs(lands[-1][1] - r[3]) > 1 or math.hypot(lands[-1][0] - r[2], lands[-1][2] - r[4]) > 3):
            lands.append((round(r[2], 2), round(r[3], 2), round(r[4], 2)))
    return dict(frame=b[0], foot=b[1], x=b[2], y=b[3], z=b[4], vx=round(vx, 2), vz=round(vz, 2), speed=round(math.hypot(vx, vz), 2),
                course_port=round(math.degrees(math.atan2(vx, vz)), 1), edge=(e[2], e[3], e[4]), lands=lands[:4], end=rows[-1][2:5])


def under(rows, step=3):
    """где игрок бота впервые оказался под землёй Intersect оригинала (ниже её поверхности на 0,5+ м, поверхность не выше 3 м
    над ним): кадр, точка (порт) и высота земли — вход под мир раньше самого провала"""
    for r in rows[::step]:
        g = [y for y, _ in ground(r[2], -r[4])]
        if any(r[3] + 0.5 < y <= r[3] + 3.0 for y in g) and not any(abs(y - r[3]) < 0.5 for y in g):
            return dict(frame=r[0], foot=r[1], at=[round(r[2], 2), round(r[3], 2), round(r[4], 2)], ground=[y for y in g if r[3] < y <= r[3] + 3][:2])
    return None


def loaders():
    """объёмы загрузки зон оригинала (ZoneEvent, тип 5, l1_terra.p3d) в координатах оригинала: что грузят (;) и что сбрасывают (:)"""
    import struct
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from p3d import read, walk, string
    out = []
    for c in walk(read(ROOT / 'hit-and-run-web/source/game/art/l1_terra.p3d')):
        if c.id != 0x3000005: continue
        name, p = string(c.data); kind, length = struct.unpack_from('<II', c.data, p)
        if kind != 5: continue
        txt = c.data[p + 8: p + 8 + length * 4].split(b'\0')[0].decode('latin-1')
        if '@' in txt: continue   # вход в интерьер
        loads = re.findall(r'(l1[zr]\w+)\.p3d;', txt); drops = re.findall(r'(l1[zr]\w+)\.p3d:', txt)
        for t in c.children:
            if t.id != 0x3000006: continue
            _, q = string(t.data); half = struct.unpack_from('<3f', t.data, q + 4); m = struct.unpack_from('<16f', t.data, q + 16)
            axes, hs = [], []
            for r in range(3):
                ax = m[r * 4: r * 4 + 3]; ln = math.sqrt(sum(a * a for a in ax)) or 1.0
                axes.append(tuple(a / ln for a in ax)); hs.append(half[r] * ln)
            out.append(dict(name=name, loads=loads, drops=drops, c=m[12:15], axes=axes, h=hs))
    return out


def in_loader(L, x, y, z):
    return [l['name'] for l in L if all(abs(sum((v - c) * a for v, c, a in zip((x, y, z), l['c'], l['axes'][k]))) <= l['h'][k] for k in range(3))]


_TRI = None


def tris():
    """земля Intersect (0x3f00003) всех зон уровня 1 в координатах оригинала: (N,3,3) и номер файла; кэш build/ps2ref/falls/intersect.npz"""
    global _TRI
    if _TRI is not None: return _TRI
    import numpy as np, struct
    cache = OUT / 'intersect.npz'
    if cache.exists():
        d = np.load(cache, allow_pickle=True); _TRI = (d['t'], d['f'], list(d['names'])); return _TRI
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from p3d import read, walk
    G = ROOT / 'hit-and-run-web/source/game/art'; T, Fi, names = [], [], []
    for k, f in enumerate(sorted(G.glob('l1r*.p3d')) + sorted(G.glob('l1z*.p3d'))):
        names.append(f.stem)
        for c in walk(read(f)):
            if c.id != 0x3f00003: continue
            ni, = struct.unpack_from('<I', c.data); idx = np.frombuffer(c.data, '<u4', ni, 4); q = 4 + 4 * ni
            nv, = struct.unpack_from('<I', c.data, q); pos = np.frombuffer(c.data, '<f4', 3 * nv, q + 4).reshape(-1, 3)
            t = pos[idx[:ni // 3 * 3]].reshape(-1, 3, 3); T.append(t); Fi.append(np.full(len(t), k))
    OUT.mkdir(parents=True, exist_ok=True)
    _TRI = (np.concatenate(T), np.concatenate(Fi), names); np.savez(cache, t=_TRI[0], f=_TRI[1], names=np.array(names)); return _TRI


def ground(x, z):
    """все высоты земли Intersect оригинала над точкой (x, z) оригинала: [(y, зона)] сверху вниз"""
    import numpy as np
    T, Fi, names = tris()
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    m = (np.minimum(np.minimum(a[:, 0], b[:, 0]), c[:, 0]) <= x) & (np.maximum(np.maximum(a[:, 0], b[:, 0]), c[:, 0]) >= x) & \
        (np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2]) <= z) & (np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2]) >= z)
    out = []
    for i in np.nonzero(m)[0]:
        A, B, C = T[i]
        d = (B[2] - C[2]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[2] - C[2])
        if abs(d) < 1e-9: continue
        l1 = ((B[2] - C[2]) * (x - C[0]) + (C[0] - B[0]) * (z - C[2])) / d
        l2 = ((C[2] - A[2]) * (x - C[0]) + (A[0] - C[0]) * (z - C[2])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-6: continue
        out.append((round(float(l1 * A[1] + l2 * B[1] + l3 * C[1]), 2), names[Fi[i]]))
    return sorted(set(out), reverse=True)


def zones_at(cov, x, z_orig, r=1):
    """файлы зон с землёй Intersect в клетках 8 м вокруг точки (координаты оригинала)"""
    gx, gz = int(math.floor(x / 8)), int(math.floor(z_orig / 8)); out = set()
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1): out |= set(cov.get(f'{gx + dx}:{gz + dz}', []))
    return sorted(out)


def top(night=None, n=20):
    import night as NI
    N = Path(night) if night else last_night()
    S = json.loads((N / 'night.json').read_text())
    regs = NI.regions({**S['explore']['clusters'], **S['chase']['stuck'], **S['chase']['corners']}, 3)
    new, fold = NI.split_known(regs, NI.known_rows())
    falls = [r for r in new if r['kind'] == 'fall'][:n]
    nm = json.loads((N / 'in/build/sandbox/colnames-l1.json').read_text())
    D = deaths_port()
    cov = json.loads((OUT / 'zonecov.json').read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, r in enumerate(falls, 1):
        tr, head = replay(N, r['repro'])
        if not tr: rows.append(dict(i=i, place=r, error='повтор пуст')); continue
        d = depart(tr, D); un = under(tr)
        path_death = sorted({in_death(D, t[2], t[3], t[4]) for t in tr if t[0] >= d['frame']} - {None})
        zd, ze = zones_at(cov, d['x'], -d['z']), zones_at(cov, d['edge'][0], -d['edge'][2], 0)
        rows.append(dict(i=i, x=r['x'], y=r['y'], z=r['z'], layer=r['layer'], objs=[NI.obj_name(o, nm) for o in r['objs'][:3]], cells=r['cells'], n=r['n'],
                         repro=r['repro'], frames=tr[-1][0], depart=d, death_on_path=path_death,
                         zones_depart=zd, zones_edge=ze, under=un,
                         orig=dict(x=round(d['x'], 2), y=round(d['y'], 2), z=round(-d['z'], 2), vx=d['vx'], vz=round(-d['vz'], 2),
                                   edge=[round(d['edge'][0], 2), round(d['edge'][1], 2), round(-d['edge'][2], 2)])))
        dd = rows[-1]
        print(f"{i:2d} {r['x']:7.1f} {r['z']:7.1f} n={r['n']:6d} {'пешком' if d['foot'] else 'машина'} ушёл с ({d['x']:.1f}, {d['y']:.1f}, {d['z']:.1f}) "
              f"{d['speed']:.1f} м/с курс {d['course_port']:.0f}° край ({d['edge'][0]:.1f}, {d['edge'][1]:.1f}, {d['edge'][2]:.1f}) посадки {d['lands'][:2]} DEATH {path_death or '-'} зоны {zd}/{ze} | {', '.join(dd['objs'])}")
    (OUT / 'top.json').write_text(json.dumps(dict(night=str(N.resolve().relative_to(ROOT)), places=rows), ensure_ascii=False, indent=1) + '\n')
    return rows


STATE = 'build/ps2ref/state_l1_incar.p2s'
TRACE = ['car_cm[0]', 'car_cm[1]', 'car_cm[2]', 'car_vel[0]', 'car_vel[1]', 'car_vel[2]', 'mat[12]', 'mat[13]', 'mat[14]']
ZONE_LOADER = {'l1r7': 'loader7', 'l1r2': 'loader3', 'l1z3': 'loader3', 'l1r3': 'loader17', 'l1z2': 'loader19', 'l1z7': 'loader8', 'l1z1': 'loader', 'l1r1': 'loader'}
T_LOAD, T_S, T_P, T_PUSH, T_END = 150, 400, 600, 630, 880   # снимок в конце S держит PINE ~35 кадров: P после него


def safe_y(x, z, near_y, lift=1.5):
    """высота установки машины: ближайшая к near_y земля Intersect под точкой (+lift), иначе near_y + lift"""
    g = [y for y, _ in ground(x, z) if y <= near_y + 2]
    return round((g[0] if g else near_y) + lift, 2)


def put(at, x, y, z, vel=(0.0, 0.0, 0.0), vhold=10):
    w = [dict(name=f'car_cm[{i}]', value=round(v, 3), at=at, hold=2) for i, v in enumerate((x, y, z))]
    return w + [dict(name=f'car_vel[{i}]', value=round(v, 3), at=at, hold=vhold) for i, v in enumerate(vel)]


def road_in(l):
    """точка дороги трафика (build/sandbox/roads-l1.bin, порт) внутри объёма загрузки, ближе всех к его центру — в координатах оригинала"""
    import struct
    b = (ROOT / 'build/sandbox/roads-l1.bin').read_bytes(); best = None
    for i in range(len(b) // 28):
        ax, ay, az, bx, by, bz, hw = struct.unpack_from('<7f', b, i * 28); k = max(1, int(math.hypot(bx - ax, bz - az) / 2))
        for j in range(k + 1):
            t = j / k; x, y, z = ax + (bx - ax) * t, ay + (by - ay) * t, -(az + (bz - az) * t)
            if in_loader([l], x, y + 1, z):
                d = math.hypot(x - l['c'][0], z - l['c'][2])
                if best is None or d < best[0]: best = (d, x, y, z)
    return best[1:] if best else None


def recipe(p, L, suffix='', hold_load=False):
    """рецепт места: (L) машина в объём загрузки зоны места, ждать 5 с; (S) машина в 2,5 м за краем по курсу, 3 с — стоит или
    падает; (P) машина в точке ухода, толчок по курсу со скоростью бота (не меньше 5 м/с) 1 с, 5 с физики — падает ли ниже −30 м"""
    import hashlib
    o = p['orig']; e = o['edge']; sp = max(5.0, p['depart']['speed'])
    ang = math.atan2(o['vx'], o['vz']) if (abs(o['vx']) + abs(o['vz'])) > 0.05 else 0.0
    dx, dz = math.sin(ang), math.cos(ang)
    inside = in_loader(L, o['x'], o['y'], o['z'])
    zone = (p['zones_depart'] or p['zones_edge'] or zones_at(json.loads((OUT / 'zonecov.json').read_text()), o['x'], o['z'], 3) or ['l1z1'])[0]
    if inside:   # точка ухода сама в объёме загрузки: ждать загрузку в 6 м позади по курсу, чтобы машина не съехала за край раньше опыта
        lx, lz, lname = o['x'] - 6 * dx, o['z'] - 6 * dz, inside[0]; ly = round(o['y'] + 1.5, 2)
        if not in_loader(L, lx, ly - 1, lz): lx, lz = o['x'], o['z']
    else:
        lname = ZONE_LOADER[zone]; l = next(v for v in L if v['name'] == lname)
        rp = road_in(l) if hold_load else None
        if rp: lx, ly, lz = rp[0], rp[1] + 1.0, rp[2]
        else: lx, lz = l['c'][0], l['c'][2]; ly = safe_y(lx, lz, l['c'][1] + l['h'][1] - 1, 1.5)
    s1 = (e[0] + 2.5 * dx, e[2] + 2.5 * dz)
    w = put(T_LOAD, lx, ly, lz, vhold=20)
    if hold_load:   # держать машину в объёме загрузки всю фазу L: удар трафика не выкинет её из загруженной зоны (f07: замерла)
        for q in w: q['hold'] = T_S - T_LOAD - 20
    gs = [y for y, _ in ground(s1[0], s1[1]) if e[1] - 1 <= y <= e[1] + 3]   # за краем — с высоты края (земля чуть выше — от неё)
    w += put(T_S, s1[0], round(max([e[1]] + gs) + 1.5, 2), s1[1])
    w += put(T_P, o['x'], round(o['y'] + 1.5, 2), o['z'])
    w += [dict(name=f'car_vel[{i}]', value=round(v, 3), at=T_PUSH, hold=50) for i, v in ((0, sp * dx), (2, sp * dz))]
    st = ROOT / STATE
    return dict(id=f"f{p['i']:02d}{suffix}", profile=1, state=STATE, state_sha256=hashlib.sha256(st.read_bytes()).hexdigest(), frames=T_END, every=1,
                trace=TRACE, writes=w, shots=[T_P - 50, T_END - 6],
                note=dict(place=p['i'], loader=lname, zone=zone, depart=[o['x'], o['y'], o['z']], edge=e, beyond=[round(s1[0], 2), round(s1[1], 2)],
                          course_orig_deg=round(math.degrees(ang), 1), speed=round(sp, 2), foot=p['depart']['foot']))


def recipes(only=None, suffix='', hold_load=False):
    T = json.loads((OUT / 'top.json').read_text()); L = loaders(); out = []
    for p in T['places']:
        if only and p['i'] not in only: continue
        r = recipe(p, L, suffix, hold_load); path = ROOT / f"tools/ps2ref/recipes/{r['id']}.json"
        path.write_text(json.dumps(r, ensure_ascii=False, indent=1) + '\n'); out.append(path)
        n = r['note']; print(r['id'], n['loader'], n['zone'], 'ушёл', n['depart'], 'за краем', n['beyond'], f"курс {n['course_orig_deg']}° {n['speed']} м/с", 'пешком' if n['foot'] else 'машина')
    return out


def phases(rid):
    """разбор трассы ответа по фазам L / S / P: где встала после телепорта, замирание, перенос (зона DEATH), минимум высоты"""
    import csv
    rows = list(csv.reader((ROOT / f'build/ps2ref/answers/{rid}/trace.tsv').open(), delimiter='\t'))
    h = rows[0]; R = [[float(x) for x in r] for r in rows[1:]]; ix = h.index
    cm = lambda r: (r[ix('car_cm[0]')], r[ix('car_cm[1]')], r[ix('car_cm[2]')])
    vel = lambda r: (r[ix('car_vel[0]')], r[ix('car_vel[1]')], r[ix('car_vel[2]')])
    apex = [(d['name'], d['apex'][0], d['apex'][1], -d['apex'][2]) for d in deaths_port()]
    out = {}
    rec = json.loads((ROOT / f'tools/ps2ref/recipes/{rid}.json').read_text())
    tgt = {w['at']: w['value'] for w in rec['writes'] if w['name'] == 'car_cm[0]'}
    for ph, a, b in (('L', T_LOAD, T_S), ('S', T_S, T_P), ('P', T_P, T_END + 40)):
        W = [r for r in R if a <= r[1] < b]
        k = next((j for j, r in enumerate(W) if abs(cm(r)[0] - tgt.get(a, 1e9)) < 0.5), None)   # с отсчёта, где телепорт пришёл
        W = W[k + 2:] if k is not None else []
        if not W: out[ph] = dict(error='нет строк'); continue
        p0 = cm(W[0]); ys = [cm(r)[1] for r in W]; ev = []
        still = 0; frozen = None
        for r0, r1 in zip(W, W[1:]):
            a0, a1 = cm(r0), cm(r1); d = math.dist(a0, a1)
            dtf = max(1.0, r1[1] - r0[1]) / 50.0   # кадры игры 50/с; снимок держит PINE ~35 кадров — это не перенос
            if d > 5 and d / dtf > 80 and not any(abs(r1[1] - t) <= 4 for t in (T_P, T_PUSH)):
                nm = min(apex, key=lambda q: math.hypot(q[1] - a1[0], q[3] - a1[2]))
                ev.append(dict(kind='перенос', frame=int(r1[1]), frm=[round(v, 2) for v in a0], to=[round(v, 2) for v in a1],
                               death=nm[0] if math.hypot(nm[1] - a1[0], nm[3] - a1[2]) < 3 else None))
            if d < 1e-3 and math.hypot(*vel(r1)) > 1.0: still += 1
            else: still = 0
            if still == 8 and frozen is None: frozen = dict(frame=int(r1[1]) - 16, at=[round(v, 2) for v in a1], vel=[round(v, 2) for v in vel(r1)])
        stuck_air = all(abs(cm(r)[1] - p0[1]) < 0.02 for r in W) and len(W) > 20
        out[ph] = dict(start=[round(v, 2) for v in p0], end=[round(v, 2) for v in cm(W[-1])], ymin=round(min(ys), 2),
                       frozen=frozen, events=ev, stuck_in_air=stuck_air)
    return out


def verdict_line(p, ph):
    """одна строка вердикта места по фазам оригинала"""
    def one(f, y0):
        if f.get('error'): return f['error']
        d = [e for e in f['events'] if e['kind'] == 'перенос']
        if f['stuck_in_air']: return 'зона не загружена (висит в воздухе)'
        if d and d[0]['death']: return f"падает, зона DEATH {d[0]['death']} ставит в {d[0]['to']}"
        if d: return f"перенос в {d[0]['to']}"
        if f['ymin'] < -30: return f"падает под мир (ymin {f['ymin']})"
        if f['frozen']: return f"замерла в {f['frozen']['at']}"
        if f['end'][1] < y0 - 3: return f"падает на землю ниже (y {f['end'][1]})"
        return f"стоит (y {f['end'][1]})"
    y0 = p['orig']['y']
    return dict(L=one(ph['L'], ph['L']['start'][1] if 'start' in ph['L'] else y0), S=one(ph['S'], y0), P=one(ph['P'], y0))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['recipes']:
        only = [int(x) for x in a[a.index('--only') + 1].split(',')] if '--only' in a else None
        recipes(only, a[a.index('--suffix') + 1] if '--suffix' in a else '', '--hold-load' in a)
    elif a[:1] == ['phases']:
        T = {p['i']: p for p in json.loads((OUT / 'top.json').read_text())['places']}
        for rid in a[1:]:
            ph = phases(rid); v = verdict_line(T[int(rid[1:3])], ph)
            print(rid, '| L:', v['L'], '| S:', v['S'], '| P:', v['P'])
            for k in 'LSP': print('   ', k, json.dumps(ph[k], ensure_ascii=False)[:400])
    elif a[:1] == ['top']:
        nt = a[a.index('--night') + 1] if '--night' in a else None
        k = int(a[a.index('--n') + 1]) if '--n' in a else 20
        top(nt, k)
    else:
        print(__doc__)
