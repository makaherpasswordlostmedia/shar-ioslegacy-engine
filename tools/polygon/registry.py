#!/usr/bin/env python3
"""Регистратор полигона v2 (план Роба docs/ПОЛИГОН_ПЛАН_2026-10-05.md: «событие -> тип и место L<N> X<r>-<s>; склейка одинаковых мест»).
Читает журналы прогонов уровня (без игры) и ведёт реестр мест уровня; ИИ читает только итог.

  python3 tools/polygon/registry.py --level N --run DIR [--run DIR2 …] [--logs DIR] [--level-shr F] [--out build/polygon/L<N>]
      -> OUT/registry.tsv (все места, с первого круга: когда найдено, сколько раз, источники), OUT/ИТОГ_L<N>.md (≤ 5 КБ, только
         расхождения по важности: застревания -> видимое -> прочее), OUT/карта.png, OUT/events.tsv (события этого вызова с типом)
      код выхода 0; в stdout последняя строка «новых мест K» (круг полигона по ней решает, насытился ли уровень)

Источники (что есть — то и читается): рой исследователей DIR/swarm/runs/*/events.tsv (tools/bots/explorer --cells-out), инспектор
DIR/inspector/*/{events,hits,interact}.tsv и trace.bin (tools/bots/inspector), догонялки DIR/chase/*/stdout.tsv (строки X,
tools/bots/chase), строки CAMIN/CAMINF журналов смоука (--logs: *.txt, *.log; правка 331), данные уровня (--level-shr: дыры, невидимые
стены, проход сквозь стену — tools/polygon/geom.py). Вердикты сверки с оригиналом — OUT/twinq.tsv (tools/polygon/twinq.py).

Типы (группа важности: 1 застревания, 2 видимое, 3 прочее) — TYPES ниже. Склейка: событие присоединяется к месту ближе MERGE_R м
по плоскости и MERGE_DY по высоте (крыша над улицей — другое место); у места — все его типы со счётом, главный — самый важный.
POLY_REG_BREAK=merge — склейка выключена (отрицательный контроль tests/polygon/run.sh: каждое событие — своё место)."""
import argparse, collections, math, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/bots')); sys.path.insert(0, str(Path(__file__).resolve().parent))
from anatomy import code   # viewer/placecode.h: буквы ABCDEFGHJKLM без I

TYPES = {   # тип: (группа, по-русски)
    'stuck_car': (1, 'машина не выезжает'),
    'stuck_foot': (1, 'Гомер заперт'),
    'through_wall': (2, 'сквозь видимую стену'),
    'invisible_wall': (2, 'невидимая стена'),
    'fall': (2, 'провал под мир'),
    'hole_visible': (2, 'дыра: видимая земля без коллизии'),
    'hole_phantom': (2, 'коллизия без видимой земли'),
    'cam_inside': (2, 'камера внутри'),
    'death': (3, 'перенос DEATH'),
    'interact_fail': (3, 'взаимодействие не сработало'),
    'chase_corner': (3, 'погоня не достаёт (угол)'),
}
GROUPS = {1: 'Застревания', 2: 'Видимое', 3: 'Прочее'}
RAW = {'car_trapped': 'stuck_car', 'foot_trapped': 'stuck_foot', 'foot_trapped_jump': 'stuck_foot', 'foot_stuck': 'stuck_foot',
       'fall': 'fall', 'death_move': 'death', 'interact_fail': 'interact_fail', 'eternal_corner': 'chase_corner',
       'pursuer_stuck': 'stuck_car'}
MERGE_R, MERGE_DY = 8.0, 2.5
LIMIT = 5000   # байт итога
MATCH = ('совпало',)   # вердикты сверки, которые не расхождение (в итог не идут)


def rank(t): return TYPES.get(t, (9, t))[0]


# ------------------------------------------------------------------ сбор событий
def _tsv(p):
    try: txt = Path(p).read_text(errors='replace')
    except OSError: return []
    return [l.split('\t') for l in txt.splitlines() if l and not l.startswith('#')]


def ev(t, x, y, z, src, obj='-', foot=0, run='-'):
    return dict(type=t, x=float(x), y=float(y), z=float(z), src=src, obj=obj or '-', foot=int(foot), run=run)


def from_cells_events(p, src, run):
    """events.tsv формата cellsout.h (вид x y z время слой объект пешком [точка])"""
    out = []
    for f in _tsv(p):
        if len(f) < 4 or f[0] not in RAW: continue
        try: out.append(ev(RAW[f[0]], f[1], f[2], f[3], src, f[6] if len(f) > 6 else '-', f[7] if len(f) > 7 else 0, run))
        except ValueError: pass
    return out


def from_chase(p, run, min_stuck=3):
    """stdout.tsv догонялок: X вид x y z раз файл слой объект. Застревание погони — где повторилось ≥ min_stuck раз (одиночное —
    промах водителя погони, как anatomy.judge_evidence)"""
    out = []
    for f in _tsv(p):
        if len(f) < 6 or f[0] != 'X' or f[1] not in RAW: continue
        try:
            n = int(f[5])
            if f[1] == 'pursuer_stuck' and n < min_stuck: continue
            for _ in range(min(n, 50)): out.append(ev(RAW[f[1]], f[2], f[3], f[4], 'chase', f[8] if len(f) > 8 else '-', 0, run))
        except ValueError: pass
    return out


CAMRE = re.compile(r'CAMINF .*?fl=(\d+).*?pivot=(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)(?:.*?foot=(\d))?')
def from_camin(paths):
    """строки CAMINF (viewer/main.c, правка 331: кадр «камера внутри», pivot — игрок) -> cam_inside; подряд идущие кадры одного
    места — одно событие на 1 м сдвига"""
    out, last = [], None
    for p in paths:
        try: txt = Path(p).read_text(errors='replace')
        except OSError: continue
        for ln in txt.splitlines():
            m = CAMRE.search(ln)
            if not m: continue
            x, y, z = float(m.group(2)), float(m.group(3)), float(m.group(4))
            if last and math.hypot(x - last[0], z - last[1]) < 1.0: continue
            last = (x, z); out.append(ev('cam_inside', x, y, z, 'camin', f'fl{m.group(1)}', int(m.group(5) or 0), Path(p).name))
    return out


def from_hits(p, geo, run):
    """удары машины о стену (inspector hits.tsv): у точки удара нет видимой геометрии -> невидимая стена"""
    out = []
    if geo is None: return out
    for f in _tsv(p):
        try: x, y, z = float(f[0]), float(f[1]), float(f[2])
        except (ValueError, IndexError): continue
        if geo.invisible(x, y, z): out.append(ev('invisible_wall', x, y, z, 'inspector', f'{["t", "b", "c", "s"][int(f[4]) % 4]}{f[5]}', 0, run))
    return out


def from_trace(p, geo, run):
    if geo is None: return []
    from geom import read_trace
    segs = read_trace(p)
    return [ev('through_wall', x, y, z, 'inspector', '-', segs[i][6], run) for x, y, z, i in geo.crossings(segs)]


def collect(runs, logs=(), geo=None):
    E = []
    for d in map(Path, runs):
        for p in sorted(d.glob('swarm/runs/*/events.tsv')): E += from_cells_events(p, 'swarm', p.parent.name)
        for p in sorted(d.glob('inspector/*/events.tsv')): E += from_cells_events(p, 'inspector', p.parent.name)
        for p in sorted(d.glob('inspector/*/hits.tsv')): E += from_hits(p, geo, p.parent.name)
        for p in sorted(d.glob('inspector/*/trace.bin')): E += from_trace(p, geo, p.parent.name)
        for p in sorted(d.glob('chase/*/stdout.tsv')): E += from_chase(p, p.parent.name)
    lp = []
    for d in map(Path, logs):
        lp += sorted(d.rglob('*.txt')) + sorted(d.rglob('*.log')) if d.is_dir() else [d]
    E += from_camin(lp)
    if geo is not None:
        for h in geo.holes(): E.append(ev(h['kind'], h['x'], h['y'], h['z'], 'data', f'n{h["cells"]}'))
    return E


# ------------------------------------------------------------------ склейка в места
def merge(events, places=None, now=None):
    """события -> места (список dict). places — прежний реестр уровня (продолжение): новое событие идёт в ближайшее место"""
    places = list(places or []); now = now or time.strftime('%Y%m%d-%H%M'); brk = os.environ.get('POLY_REG_BREAK') == 'merge'
    for p in places: p['seen_now'] = 0
    new = 0
    for e in sorted(events, key=lambda e: (rank(e['type']), e['type'], e['x'], e['z'], e['y'])):
        best, bd = None, MERGE_R
        if not brk:
            for p in places:
                d = math.hypot(p['x'] - e['x'], p['z'] - e['z'])
                if d <= bd and abs(p['y'] - e['y']) <= MERGE_DY: best, bd = p, d
        if best is None:
            best = dict(x=e['x'], y=e['y'], z=e['z'], n=0, types=collections.Counter(), srcs=set(), objs=collections.Counter(),
                        first=now, last=now, seen_now=0, verdict='-', twin='-', new=True)
            places.append(best); new += 1
        k = best['n']
        best['x'] = (best['x'] * k + e['x']) / (k + 1); best['z'] = (best['z'] * k + e['z']) / (k + 1); best['y'] = (best['y'] * k + e['y']) / (k + 1)
        best['n'] += 1; best['seen_now'] += 1; best['types'][e['type']] += 1; best['srcs'].add(e['src']); best['last'] = now
        if e['obj'] != '-': best['objs'][e['obj']] += 1
    for p in places: p['main'] = min(p['types'], key=lambda t: (rank(t), -p['types'][t], t)) if p['types'] else '-'
    return places, new


def name_places(places, level):
    """код места L<N> X<r>-<s>; два места в одном участке 33 м (крыша над улицей) — «/2», «/3» по высоте снизу вверх"""
    by = collections.defaultdict(list)
    for p in places: p['code'] = code(p['x'], p['z']); by[p['code']].append(p)
    for c, ps in by.items():
        ps.sort(key=lambda p: (p['y'], p['x'], p['z']))
        for i, p in enumerate(ps): p['id'] = f'L{level} {c}' + (f'/{i + 1}' if i else '')
    return places


# ------------------------------------------------------------------ реестр на диске
HEAD = '# место\tx\ty\tz\tглавный\tтипы\tисточники\tобъекты\tраз\tпервый\tпоследний\tвердикт\tкадры\n'
def save(places, path):
    L = [HEAD]
    for p in sorted(places, key=lambda p: (rank(p['main']), -p['n'], p['id'])):
        L.append('\t'.join([p['id'], f'{p["x"]:.1f}', f'{p["y"]:.1f}', f'{p["z"]:.1f}', p['main'],
                            ','.join(f'{t}:{n}' for t, n in sorted(p['types'].items())), ','.join(sorted(p['srcs'])) or '-',
                            ','.join(f'{o}:{n}' for o, n in p['objs'].most_common(4)) or '-', str(p['n']), p['first'], p['last'],
                            p.get('verdict', '-'), p.get('twin', '-')]) + '\n')
    Path(path).write_text(''.join(L))


def load(path):
    out = []
    for f in _tsv(path):
        if len(f) < 13: continue
        cnt = lambda s: collections.Counter({k: int(v) for k, v in (x.rsplit(':', 1) for x in s.split(',') if ':' in x)}) if s != '-' else collections.Counter()
        out.append(dict(id=f[0], x=float(f[1]), y=float(f[2]), z=float(f[3]), main=f[4], types=cnt(f[5]), srcs=set(f[6].split(',')) - {'-'},
                        objs=cnt(f[7]), n=int(f[8]), first=f[9], last=f[10], verdict=f[11], twin=f[12]))
    return out


def apply_verdicts(places, twinq):
    """вердикты очереди сверки (OUT/twinq.tsv: место … вердикт кадры) -> места"""
    vv = {}
    for f in _tsv(twinq):
        if len(f) >= 4: vv[f[0]] = (f[-2], f[-1])
    for p in places:
        if p['id'] in vv: p['verdict'], p['twin'] = vv[p['id']]


# ------------------------------------------------------------------ итог ≤ 5 КБ
def summary(places, level, new, out_md, extra=()):
    lines = [f'# L{level} · полигон · итог {time.strftime("%d.%m %H:%M")} · только расхождения (полный список — registry.tsv)']
    shown = [p for p in places if p.get('verdict', '-') not in MATCH]
    nm = sum(1 for p in places if p.get('verdict', '-') in MATCH)
    nv = sum(1 for p in places if p.get('verdict', '-') not in ('-', 'не сверено'))
    lines.append(f'мест {len(places)}, новых за круг {new}; сверено с PS2 {nv}, из них совпало {nm} (в итоге их нет); карта: карта.png')
    lines += list(extra)
    body, cut = [], 0
    for g in (1, 2, 3):
        ps = sorted([p for p in shown if rank(p['main']) == g], key=lambda p: (-p['n'], p['id']))
        if not ps: continue
        body.append(f'\n## {g}. {GROUPS[g]} — мест {len(ps)}')
        for p in ps:
            ts = ', '.join(f'{TYPES.get(t, (0, t))[1]} ×{n}' for t, n in sorted(p['types'].items(), key=lambda kv: (rank(kv[0]), -kv[1])))
            ob = (' · ' + ', '.join(o for o, _ in p['objs'].most_common(2))) if p['objs'] else ''
            v = p.get('verdict', '-'); v = 'не сверено' if v == '-' else v
            body.append(f'- {p["id"]} · x {p["x"]:.0f} z {p["z"]:.0f} y {p["y"]:.1f} · {ts}{ob} · PS2: {v}' + ('' if p.get('twin', '-') == '-' else f' · {p["twin"]}')
                        + (' · НОВОЕ' if p.get('new') else ''))
    txt = '\n'.join(lines) + '\n'
    for i, b in enumerate(body):
        tail = f'… ещё {sum(1 for x in body[i:] if x.startswith("- "))} мест — registry.tsv\n'
        if len((txt + b + '\n').encode()) + len(tail.encode()) > LIMIT:
            txt += tail; cut = 1; break
        txt += b + '\n'
    Path(out_md).write_text(txt)
    return len(txt.encode()), cut


# ------------------------------------------------------------------ карта
def render_map(places, geo, level, path):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    X0, Z0, CELL, LET = -700.0, -700.0, 100.0, 'ABCDEFGHJKLM'
    xs = [p['x'] for p in places]; zs = [p['z'] for p in places]
    if geo is not None and len(geo.Rs): xs += [float(geo.Rs[:, 0].min()), float(geo.Rs[:, 0].max())]; zs += [float(geo.Rs[:, 2].min()), float(geo.Rs[:, 2].max())]
    if not xs: xs, zs = [0.0], [0.0]
    ca, cb = max(0, math.floor((min(xs) - X0) / CELL)), min(12, math.floor((max(xs) - X0) / CELL) + 1)
    ra, rb = max(0, math.floor((min(zs) - Z0) / CELL)), min(15, math.floor((max(zs) - Z0) / CELL) + 1)
    PX, PAD = 1.5, 40
    W, H = int((cb - ca) * CELL * PX) + 2 * PAD, int((rb - ra) * CELL * PX) + 2 * PAD
    ex = lambda x: PAD + (x - (X0 + ca * CELL)) * PX
    ez = lambda z: PAD + (z - (Z0 + ra * CELL)) * PX
    img = np.full((H, W, 3), 246, np.uint8)
    if geo is not None and len(geo.Rs):   # подложка: видимое сверху, выше — темнее
        R = geo.Rs; ix = np.clip(ex(R[:, 0]).astype(int), 0, W - 1); iz = np.clip(ez(R[:, 2]).astype(int), 0, H - 1)
        y = R[:, 1]; t = np.clip((y - np.percentile(y, 5)) / max(1e-3, np.percentile(y, 95) - np.percentile(y, 5)), 0, 1)
        o = np.argsort(y); img[iz[o], ix[o]] = (225 - 90 * t[o])[:, None].astype(np.uint8)
    im = Image.fromarray(img); dr = ImageDraw.Draw(im)
    try: font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
    except OSError: font = ImageFont.load_default()
    for c in range(ca, cb + 1):
        X = ex(X0 + c * CELL); dr.line([X, PAD, X, H - PAD], fill=(200, 60, 40), width=1)
        if c < cb: dr.text((ex(X0 + (c + .5) * CELL), 8), LET[c], fill=(200, 60, 40), font=font)
    for r in range(ra, rb + 1):
        Z = ez(Z0 + r * CELL); dr.line([PAD, Z, W - PAD, Z], fill=(200, 60, 40), width=1)
        if r < rb: dr.text((8, ez(Z0 + (r + .5) * CELL)), str(r + 1), fill=(200, 60, 40), font=font)
    COL = {1: (220, 20, 30), 2: (130, 0, 190), 3: (240, 150, 0)}
    shown = sorted([p for p in places if p.get('verdict', '-') not in MATCH], key=lambda p: (rank(p['main']), -p['n']))
    for i, p in enumerate(shown):
        g = rank(p['main']); r = 4 + min(6, int(math.log2(1 + p['n'])))
        dr.ellipse([ex(p['x']) - r, ez(p['z']) - r, ex(p['x']) + r, ez(p['z']) + r], fill=COL.get(g, (90, 90, 90)), outline=(255, 255, 255))
        if i < 60: dr.text((ex(p['x']) + r + 1, ez(p['z']) - 7), p['id'].split(' ', 1)[1], fill=(30, 30, 30), font=font)
    dr.text((PAD, H - PAD + 12), f'L{level}: красный — застревания, фиолетовый — видимое, оранжевый — прочее; размер — сколько раз', fill=(30, 30, 30), font=font)
    im.save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, required=True, choices=range(1, 8)); ap.add_argument('--run', action='append', default=[])
    ap.add_argument('--logs', action='append', default=[]); ap.add_argument('--level-shr'); ap.add_argument('--out')
    ap.add_argument('--no-map', action='store_true')
    a = ap.parse_args()
    out = Path(a.out or ROOT / f'build/polygon/L{a.level}'); out.mkdir(parents=True, exist_ok=True)
    geo = None
    if a.level_shr and Path(a.level_shr).exists():
        from geom import Geo
        geo = Geo.from_level(a.level_shr)
    E = collect(a.run, a.logs, geo)
    with (out / 'events.tsv').open('w') as f:
        f.write('# тип\tx\ty\tz\tисточник\tобъект\tпешком\tпрогон\n')
        for e in E: f.write(f'{e["type"]}\t{e["x"]:.2f}\t{e["y"]:.2f}\t{e["z"]:.2f}\t{e["src"]}\t{e["obj"]}\t{e["foot"]}\t{e["run"]}\n')
    places, new = merge(E, load(out / 'registry.tsv'))
    name_places(places, a.level); apply_verdicts(places, out / 'twinq.tsv'); save(places, out / 'registry.tsv')
    c = collections.Counter(e['type'] for e in E)
    extra = ['событий этого круга: ' + (', '.join(f'{TYPES[t][1]} {n}' for t, n in sorted(c.items(), key=lambda kv: rank(kv[0]))) or 'нет'),
             'не покрыто: стейтпропы (удар машиной по каждому), гэги и двери комнат изнутри, NPC/трафик в инспекторе, ' +
             ('данные уровня есть' if geo is not None else 'дыры по данным (нет --level-shr)')]
    size, cut = summary(places, a.level, new, out / f'ИТОГ_L{a.level}.md', extra)
    if not a.no_map:
        try: render_map(places, geo, a.level, out / 'карта.png')
        except Exception as e: print(f'карта не нарисована: {e}', file=sys.stderr)
    print(f'L{a.level}: событий {len(E)}, мест {len(places)}, итог {size} байт{" (обрезан)" if cut else ""} -> {out}')
    print(f'новых мест {new}')


if __name__ == '__main__':
    main()
