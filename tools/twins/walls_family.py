#!/usr/bin/env python3
"""Сверка «постановка машины» (tools/twins/placement.py) по СЕМЕЙСТВАМ коллизии (аудит пропусков 09.10, пункт 5).

Каждую расходящуюся проверку (порт пускает / PS2 пускает / толкает в разные стороны) привязываем к объекту коллизии порта
(COL1 level.shr: тип примитива, материал, флаги забора, имя сущности диска — tools/cartest/colnames.py), который стоит у
машины в момент расхождения, и к рельефу под ней (наклон земли, ступень). Сама сверка — числа placement.py (пробы оригинала
orig.jsonl не трогаем, порт — port.jsonl текущего кода).

  python3 tools/twins/walls_family.py --level 1 [--port port.jsonl] [--out DIR]
      -> DIR/families.tsv (проверка → семейство и соседи), DIR/families.json (сводка)

Оси: всё в осях порта (z порта = −z оригинала). Кузов 1,8 × 4,4 м (как probe в placement_light.c)."""
import argparse, json, math, os, struct, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C          # noqa: E402
import placement as PL      # noqa: E402

HW, HL = 0.9, 2.2           # полукузов (placement_light.c probe)
NEAR = 1.0                  # м: примитив ближе этого к прямоугольнику кузова — сосед
BAND = (0.2, 2.0)           # слой кузова над землёй точки, м
HEDGE_TOL = 0.5          # м: изгородь в лоб — центр кузова порта по нормали забора от PS2 (кузов PS2 и порта отличаются на 0,1–0,3 м)
MIXED = 1.5             # м: другой забор ближе к центру кузова в начале разгона — проба смешанная (back_cross)
BAD = ('порт пускает, PS2 нет', 'PS2 пускает, порт нет', 'выталкивает в разные стороны')


def read_col(level):
    lv = C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
    b = lv.read_bytes(); co = struct.unpack_from('<I', b, 92)[0]
    assert b[co:co + 4] == b'COL1', 'нет COL1'
    ox, oz, cell, W, H, ntri, nbox, ncyl, nseg, nref, flags = struct.unpack_from('<3f8I', b, co + 4)
    p = co + 48
    tri = np.frombuffer(b, '<f4', ntri * 12, p).reshape(-1, 12).astype(np.float64); p += ntri * 48
    box = np.frombuffer(b, '<f4', nbox * 16, p).reshape(-1, 16).astype(np.float64); p += nbox * 64
    cyl = np.frombuffer(b, '<f4', ncyl * 12, p).reshape(-1, 12).astype(np.float64); p += ncyl * 48
    seg = np.frombuffer(b, '<f4', nseg * 8, p).reshape(-1, 8).astype(np.float64)
    return dict(tri=tri, box=box, cyl=cyl, seg=seg, sha=C.sha256(lv, 16))


def col_names(level, out):
    f = out / f'colnames-l{level}.json'
    if not f.exists():
        subprocess.run([sys.executable, str(C.WT / 'tools/cartest/colnames.py'), '--level', str(level), '--out', str(f),
                        '--level-shr', str(C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr'))],
                       check=True, cwd=C.WT, capture_output=True)
    return json.loads(f.read_text())


def rect_pts(cx, cz, h, n=(9, 5)):
    fx, fz = math.sin(h), math.cos(h); rx, rz = -fz, fx
    a = np.linspace(-HL, HL, n[0]); c = np.linspace(-HW, HW, n[1])
    A, Cc = np.meshgrid(a, c)
    return np.c_[cx + A.ravel() * fx + Cc.ravel() * rx, cz + A.ravel() * fz + Cc.ravel() * rz]


def d_seg(P, a, b):
    ab = b - a; L2 = float(ab @ ab) or 1e-12
    t = np.clip(((P - a) @ ab) / L2, 0, 1)
    return np.hypot(*(P - (a + t[:, None] * ab)).T)


def hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 4))))
    if len(pts) < 3: return np.array(pts)
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def d_poly(P, poly):
    if len(poly) < 3:
        return np.min([d_seg(P, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))], 0) if len(poly) > 1 else np.hypot(*(P - poly[0]).T)
    inside = np.ones(len(P), bool); d = np.full(len(P), 1e9)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        inside &= ((b[0] - a[0]) * (P[:, 1] - a[1]) - (b[1] - a[1]) * (P[:, 0] - a[0])) >= 0
        d = np.minimum(d, d_seg(P, a, b))
    return np.where(inside, 0.0, d)


class World:
    def __init__(self, level, out):
        self.c = read_col(level); self.names = col_names(level, out)
        B = self.c['box']; self.box_poly, self.box_y = [], []
        for r in B:
            c, A, h = r[0:3], r[3:12].reshape(3, 3), r[12:15]
            corners = np.array([c + sx * h[0] * A[0] + sy * h[1] * A[1] + sz * h[2] * A[2] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
            self.box_poly.append(hull(corners[:, [0, 2]])); self.box_y.append((corners[:, 1].min(), corners[:, 1].max()))
        Y = self.c['cyl']
        self.cyl_a = Y[:, 0:3] - Y[:, 3:6] * Y[:, 7:8]; self.cyl_b = Y[:, 0:3] + Y[:, 3:6] * Y[:, 7:8]
        T = self.c['tri']; self.wall = np.nonzero(T[:, 10] < C_WALK_NY)[0]   # n.y < 0,5 — стена (col.h COL_WALK_NY)
        self.bc = np.array([(p[:, 0].min() + p[:, 0].max()) / 2 for p in self.box_poly]) if len(B) else np.zeros(0)
        self.bz = np.array([(p[:, 1].min() + p[:, 1].max()) / 2 for p in self.box_poly]) if len(B) else np.zeros(0)

    def name(self, kind, i):
        if kind == 'box': L = self.names['box']
        elif kind == 'cyl': L = self.names['cyl']
        else: return '-'
        return L[i][0] if i < len(L) else 'AnimCollision'   # хвост COL1 — объёмы AnimCollision (colnames.py)

    def scene(self, kind, i):
        L = self.names.get(kind, [])
        return L[i][1] if i < len(L) else '-'

    def near(self, cx, cz, h, gy, rad=NEAR, mv=None):
        """примитивы ближе rad к прямоугольнику кузова (центр, курс порта) в слое кузова над землёй gy -> [(dist, kind, idx, info)]"""
        P = rect_pts(cx, cz, h); out = []; ylo, yhi = gy + BAND[0], gy + BAND[1]
        R = HL + rad + 0.5
        S = self.c['seg']
        for i in np.nonzero(np.minimum(np.hypot(S[:, 0] - cx, S[:, 1] - cz), np.hypot(S[:, 2] - cx, S[:, 3] - cz)) < 200)[0]:
            g = S[i]; a, b = g[0:2], g[2:4]
            d = float(d_seg(P, a, b).min())
            if d > rad: continue
            if g[7] < ylo and g[7] < 1e5: continue
            side = float((np.array([cx, cz]) - a) @ g[4:6])
            fam = 'изгородь' if g[6] < -1.5e6 else ('граница' if g[7] > 1e5 else 'внутр')
            app = round(float(mv[0] * g[4] + mv[1] * g[5]), 2) if mv is not None else None   # < 0 — едет на линию с лица, > 0 — с изнанки к лицу
            out.append((d, 'seg', int(i), dict(fam=fam, side='лицо' if side >= 0 else 'изнанка', top=round(float(g[7]) - gy, 2) if g[7] < 1e5 else None,
                                                cu=round(side, 2), mv_n=app)))
        B = self.c['box']
        for i in np.nonzero(np.hypot(self.bc - cx, self.bz - cz) < R + 60)[0]:
            y0, y1 = self.box_y[i]
            if y1 < ylo or y0 > yhi: continue
            d = float(d_poly(P, self.box_poly[i]).min())
            if d > rad: continue
            ny = float(abs(B[i][3:12].reshape(3, 3)[:, 1]).max())
            out.append((d, 'box', int(i), dict(mat=int(B[i][15]), top=round(y1 - gy, 2), bot=round(y0 - gy, 2), name=self.name('box', i), scene=self.scene('box', i), upright=round(ny, 2))))
        Y = self.c['cyl']
        for i in np.nonzero(np.hypot(Y[:, 0] - cx, Y[:, 2] - cz) < R + 30)[0]:
            a, b, r = self.cyl_a[i], self.cyl_b[i], Y[i][6]
            if max(a[1], b[1]) + r < ylo or min(a[1], b[1]) - r > yhi: continue
            d = float((d_seg(P, a[[0, 2]], b[[0, 2]]) - r).min()) if np.hypot(*(b - a)[[0, 2]]) > 1e-3 else float(np.hypot(*(P - a[[0, 2]]).T).min() - r)
            if d > rad: continue
            out.append((max(d, 0.0), 'cyl', int(i), dict(mat=int(Y[i][9]), top=round(max(a[1], b[1]) + r - gy, 2), name=self.name('cyl', i), scene=self.scene('cyl', i),
                                                          flat=int(Y[i][8]), r=round(float(r), 2), lying=int(abs(Y[i][4]) < .7))))
        T = self.c['tri']; W = self.wall
        cen = T[W][:, [0, 3, 6]].mean(1), T[W][:, [2, 5, 8]].mean(1)
        for j in np.nonzero(np.hypot(cen[0] - cx, cen[1] - cz) < R + 20)[0]:
            i = W[j]; t = T[i]; ys = t[[1, 4, 7]]
            if ys.max() < ylo or ys.min() > yhi: continue
            poly = hull(np.array([[t[0], t[2]], [t[3], t[5]], [t[6], t[8]]]))
            d = float(d_poly(P, poly).min()) if len(poly) >= 2 else 9.0
            if d > rad: continue
            out.append((d, 'tri', int(i), dict(top=round(float(ys.max()) - gy, 2), ny=round(float(t[10]), 2))))
        out.sort(key=lambda q: q[0])
        return out


C_WALK_NY = 0.5


def trace_rows(sd, tid, phase):
    out = []
    for l in (C.DATA / sd / 'trace.tsv').read_text().splitlines()[1:]:
        c = l.split('\t')
        if c[1] == tid and c[2] == phase: out.append((int(c[0]), float(c[3]), float(c[4]), -float(c[5]), float(c[7])))
    return out


FAMILIES = [
    ('hedge', 'изгородь и куст (решение Роба 173: насквозь — не трогаем)'),
    ('back', 'забор с изнанки: машина за линией едет на лицо'),
    ('face', 'забор с лица (внутренний или граница карты)'),
    ('low', 'низкий твёрдый объём (верх ниже 0,8 м: трамплин, бордюр, плита)'),
    ('high', 'высокий твёрдый объём (ящик, капсула, стена-треугольник)'),
    ('jerk', 'у порта объекта нет, PS2 выбрасывает рывком (≥ 6 м/с)'),
    ('drift', 'у порта объекта нет, PS2 сползает (< 6 м/с: скат, бордюр, посадка с высоты)'),
]


def family_of(nb, kind, back, vmax_o):
    """соседи (ближние примитивы COL1 порта) + вид точки + переезд забора с изнанки у PS2 + рывок PS2 -> ключ семьи (FAMILIES).
    Порядок: изгородь (любой примитив листвы рядом или точка-изгородь) -> забор с изнанки -> ближайший примитив -> нет объекта"""
    if kind == 'hedge' or any((k == 'seg' and inf['fam'] == 'изгородь') or (k in ('box', 'cyl') and inf.get('mat')) for d, k, i, inf in nb):
        return 'hedge'
    if back or (nb and nb[0][1] == 'seg' and nb[0][3]['side'] == 'изнанка'): return 'back'
    if not nb: return 'jerk' if vmax_o >= 6.0 else 'drift'
    d, k, i, inf = nb[0]
    if k == 'seg': return 'face'
    return 'low' if inf['top'] < 0.8 else 'high'


def analyse(level, port_name='port.jsonl', trials_name='trials.tsv', out=None, name='now'):
    od = PL.out_dir(level); out = Path(out or od / 'families'); out.mkdir(parents=True, exist_ok=True)
    W = World(level, out)
    pts = {p['id']: p for p in PL.load_points(level)}
    O = {r['id']: r for r in PL.orig_records(level)}
    PLr = PL.jsonl(od / port_name); Pm = {g['id']: g for g in PLr[1:]}
    lines = (od / trials_name).read_text().splitlines()
    S = W.c['seg']
    hdr = lines[0].split('\t'); rows = [dict(zip(hdr, l.split('\t'))) for l in lines[1:]]
    res = []
    for t in rows:
        if t['verdict'] not in BAD: continue
        tid, tag = t['trial'][:-1], t['trial'][-1]
        r = O[tid]; g = Pm[t['trial']]; p = pts[t['point']]; gy = p['y']
        place = t['test'].startswith('постановка')
        sk, gk = ('settled', 'gassed') if tag == 'f' else ('settled2', 'reversed')
        ph = ('settle' if tag == 'f' else 'settle2') if place else ('gas' if tag == 'f' else 'rev')
        tr = trace_rows(r['session'], tid, ph)
        # где расхождение: постановка — точка постановки; разгон — где встала (упёрлась) та сторона, что упёрлась
        if place:
            B = r['before' if tag == 'f' else 'before2']
            cx, cz = g['ask'][0], g['ask'][2]; h = g['ask'][3]
            ps2_end = r[sk]['pos']; port_end = (g['settled']['x'], g['settled']['z'])
            dvec = (ps2_end[0] - (r['P'][0] - (B['cm'][0] - B['pos'][0])), -(ps2_end[2] - (r['P'][2] - (B['cm'][2] - B['pos'][2]))))
        else:
            ps2_end = r[gk]['pos']; port_end = (g['gassed']['x'], g['gassed']['z'])
            if t['verdict'].startswith('порт'): cx, cz = ps2_end[0], -ps2_end[2]
            else: cx, cz = port_end
            h = g['gassed']['h'] if not t['verdict'].startswith('порт') else C.port_h_of_yaw(r[gk]['yaw'])
            dvec = None
        if place: mv = None
        else:
            sg = 1 if tag == 'f' else -1; hh = C.port_h_of_yaw(r[sk]['yaw']); mv = (sg * math.sin(hh), sg * math.cos(hh))
        nb = W.near(cx, cz, h, gy, mv=mv)
        drop = (max(q[2] for q in tr) - min(q[2] for q in tr)) if tr else 0.0
        vmax = 0.0
        for a, b in zip(tr[2:], tr[3:]):
            dt = (b[0] - a[0]) / PL.ORIG_FPS
            if dt > 0: vmax = max(vmax, math.dist(a[1:4], b[1:4]) / dt)
        back = back_cross(S, r, tag) if not place else []
        vo = float(t.get('vmax_o') or 0.0)
        fam = family_of(nb, p['kind'], back, vo if place else 0.0)
        res.append(dict(trial=t['trial'], point=t['point'], kind=p['kind'], code=p['code'], test=t['test'], verdict=t['verdict'],
                        push_o=t.get('push_o'), push_p=t.get('push_p'), vmax_o=t.get('vmax_o'), prog_o=t.get('prog_o'), prog_p=t.get('prog_p'),
                        ps2_dy=round(drop, 2), ps2_vmax=round(vmax, 1), push_dir=[round(v, 2) for v in dvec] if dvec else None,
                        family=fam, near=[(round(d, 2), k, i, inf) for d, k, i, inf in nb[:6]], at=[round(cx, 2), round(cz, 2), round(h, 3)],
                        layer=p['layer'], nlayers=p['nlayers'], regions=p['regions'], zone=r.get('zone')))
    with (out / f'families_{name}.tsv').open('w') as fo:
        fo.write('проверка\tточка\tвид\tклетка\tтест\tитог\tсемейство\tps2_сдвиг\tps2_рывок\tps2_перепад_y\tпорт_сдвиг\tпуть_ps2\tпуть_порт\tсоседи\n')
        for q in res:
            nbs = '; '.join(f"{k}{i}:{d}м:{','.join(f'{a}={b}' for a, b in inf.items())}" for d, k, i, inf in q['near'])
            fo.write(f"{q['trial']}\t{q['point']}\t{q['kind']}\t{q['code']}\t{q['test']}\t{q['verdict']}\t{q['family']}\t{q['push_o']}\t{q['vmax_o']}\t"
                     f"{q['ps2_dy']}\t{q['push_p']}\t{q['prog_o']}\t{q['prog_p']}\t{nbs}\n")
    summ = {}
    for q in res: summ.setdefault(q['family'], {}).setdefault(q['verdict'], []).append(q['trial'])
    (out / f'families_{name}.json').write_text(json.dumps(dict(time=C.clock(), col_sha=W.c['sha'], port=PLr[0].get('meta') if PLr else {}, trials=res,
                                                       by_family=summ), ensure_ascii=False, indent=1))
    return res, summ


def seg_side(S, i, x, z):
    g = S[i]; a = g[0:2]; d = g[2:4] - a; L = float(np.hypot(*d)) or 1e-9
    return float((x - a[0]) * g[4] + (z - a[1]) * g[5]), float(((x - a[0]) * d[0] + (z - a[1]) * d[1]) / L), L


def back_cross(S, r, tag, behind=6.0, inner=True):
    """проба оригинала -> заборы, которые машина PS2 на разгоне переехала С ИЗНАНКИ НА ЛИЦО: центр кузова в начале разгона за
    линией (до behind м) в пределах звена, в конце — на лице, путь центра пересёк линию в пределах звена. Изгороди (y0 листвы,
    правка 173) не в счёт — их семья отдельная; inner — только внутренние (граница карты — отдельный открытый вопрос). -> [(номер забора, cu начала, cu конца)]"""
    sk, gk = ('settled', 'gassed') if tag == 'f' else ('settled2', 'reversed')
    if sk not in r or gk not in r: return []
    x0, z0 = r[sk]['pos'][0], -r[sk]['pos'][2]; x1, z1 = r[gk]['pos'][0], -r[gk]['pos'][2]
    out = []
    for i in np.nonzero(np.minimum(np.hypot(S[:, 0] - x0, S[:, 1] - z0), np.hypot(S[:, 2] - x0, S[:, 3] - z0)) < 120)[0]:
        if S[i][6] < -1.5e6 or (inner and S[i][7] > 1e5): continue
        c0, t0, L = seg_side(S, i, x0, z0); c1, t1, _ = seg_side(S, i, x1, z1)
        if not (-behind <= c0 < 0.0 and c1 > 0.0 and 0.0 <= t0 <= L): continue
        tc = t0 + (t1 - t0) * (-c0) / (c1 - c0)
        if 0.0 <= tc <= L: out.append((int(i), round(c0, 2), round(c1, 2)))
    if out:   # смешанный случай: в начале разгона кузов PS2 уже у другого забора (ближе MIXED к центру) — это семья «забор с лица»
        P0 = np.array([[x0, z0]]); mine = {i for i, _, _ in out}
        for j in np.nonzero(np.minimum(np.hypot(S[:, 0] - x0, S[:, 1] - z0), np.hypot(S[:, 2] - x0, S[:, 3] - z0)) < 120)[0]:
            if int(j) in mine or S[j][6] < -1.5e6: continue
            if float(d_seg(P0, S[j][0:2], S[j][2:4])[0]) < MIXED: return []
    return out


def run_side(level, tag, cflags=''):
    """порт текущего кода (cflags — флаги прежнего поведения) по всем пробам оригинала -> (точки, проверки, сводка, пробы порта)"""
    od = PL.out_dir(level); keep = {f: (od / f).read_bytes() for f in ('trials.tsv', 'compare.tsv') if (od / f).exists()}
    os.environ['PLACEMENT_CFLAGS'] = cflags
    try:
        PL.run_port(level, out_name=f'port_{tag}.jsonl')
        PT, rows, summ = PL.compare(level, port_name=f'port_{tag}.jsonl')
    finally:
        os.environ.pop('PLACEMENT_CFLAGS', None)
        for f in ('trials.tsv', 'compare.tsv'):
            if (od / f).exists(): (od / f).rename(od / f.replace('.tsv', f'_{tag}.tsv'))
        for f, b in keep.items(): (od / f).write_bytes(b)
    Pm = {g['id']: g for g in PL.jsonl(od / f'port_{tag}.jsonl')[1:]}
    return PT, rows, summ, Pm


def gate(level, cflags=''):
    """гейт «стены по PS2» по всем сверенным точкам (137 L1): (1) расходящихся точек не больше базы tests/walls/ps2_placement_base.json,
    (2) ни одна совпадавшая в базе точка не разошлась, (3) семья «забор с изнанки»: в каждой пробе, где машина PS2 переехала забор с
    изнанки на лицо (back_cross) и обе машины начали разгон из одного места (≤ 3 м), машина порта тоже на лице этого забора в конце
    разгона (меряем: центр кузова порта по нормали забора > 0). cflags — красный контроль (-DCOL_FENCE_BACK_OLD=1 обязан упасть по (3))"""
    tag = 'red' if cflags else 'gate'
    PT, rows, summ, Pm = run_side(level, tag, cflags)
    base = json.loads((C.WT / 'tests/walls/ps2_placement_base.json').read_text())
    bad = lambda c: c not in ('совпало', 'неясно', 'не сверено')
    now = {q['id']: q['cat'] for q in PT}
    common = [k for k in now if k in base['points']]
    was = sum(1 for k in common if bad(base['points'][k])); cur = sum(1 for k in common if bad(now[k]))
    new = [k for k in common if bad(now[k]) and not bad(base['points'][k])]
    S = read_col(level)['seg']; O = {r['id']: r for r in PL.orig_records(level)}
    rowmap = {(x['trial'], x['test']): x for x in rows}
    fam, fails = [], []
    for tid, r in sorted(O.items()):
        for tag_ in ('f', 'r'):
            xs = back_cross(S, r, tag_)
            if not xs: continue
            g = Pm.get(tid + tag_); test = 'разгон вперёд' if tag_ == 'f' else 'разгон назад'
            v = rowmap.get((tid + tag_, test))
            if g is None or v is None or v['verdict'] == 'не сверено' or 'разных мест' in v.get('why', ''): continue
            for i, c0, c1 in xs:
                pc, _, _ = seg_side(S, i, g['gassed']['x'], g['gassed']['z'])
                fam.append(dict(trial=tid + tag_, seg=i, ps2=[c0, c1], port_end=round(pc, 2), verdict=v['verdict']))
                if pc <= 0.0: fails.append(fam[-1])
    # правка 421: изгородь в лоб — забор-изгородь (y0 листвы), PS2 разгоняется на линию с лица почти перпендикулярно (|курс·n| > 0,9)
    # и встаёт (v < 1 м/с): машина порта встаёт там же — центр кузова по нормали в пределах HEDGE_TOL от PS2
    hed, hfail = [], []
    for tid, r in sorted(O.items()):
        for tag_ in ('f', 'r'):
            sk, gk = ('settled', 'gassed') if tag_ == 'f' else ('settled2', 'reversed')
            g = Pm.get(tid + tag_); test = 'разгон вперёд' if tag_ == 'f' else 'разгон назад'
            v = rowmap.get((tid + tag_, test))
            if g is None or v is None or sk not in r or gk not in r or v['verdict'] == 'не сверено' or 'разных мест' in v.get('why', ''): continue
            if abs(r[gk]['v']) >= 1.0: continue
            x0, z0 = r[sk]['pos'][0], -r[sk]['pos'][2]; x1, z1 = r[gk]['pos'][0], -r[gk]['pos'][2]
            sg = 1 if tag_ == 'f' else -1; hh = C.port_h_of_yaw(r[sk]['yaw']); mv = (sg * math.sin(hh), sg * math.cos(hh))
            for i in np.nonzero(S[:, 6] < -1.5e6)[0]:
                c0, t0, L = seg_side(S, i, x0, z0)
                if not (1.5 < c0 < 6.0 and 0 <= t0 <= L): continue
                if mv[0] * S[i][4] + mv[1] * S[i][5] > -0.9: continue
                c1, _, _ = seg_side(S, i, x1, z1); pc, _, _ = seg_side(S, i, g['gassed']['x'], g['gassed']['z'])
                hed.append(dict(trial=tid + tag_, seg=int(i), ps2_end=round(c1, 2), port_end=round(pc, 2)))
                if abs(pc - c1) > HEDGE_TOL: hfail.append(hed[-1])
    # (4) склон (09.10, агент физики): постановки, где машина PS2 к «settled» ещё катится (v ≥ 0,5 м/с, на колёсах, без падения), —
    # порт стоит (v < 0,2 и сдвиг < 0,5 м) реже, чем код до правки покоя на склоне (база slope_standing, -DCAR_SLOPE_HOLD_OLD=1)
    slope_tot, slope_still = 0, []
    for tid, r in sorted(O.items()):
        for k, suf in (('settled', 'f'), ('settled2', 'r')):
            s = r.get(k); g = Pm.get(tid + suf)
            if not s or not g or 'settled' not in g or s['v'] < 0.5 or abs(s['vy']) > 0.5 or s['upy'] < 0.85: continue
            slope_tot += 1; pl, st = g['placed'], g['settled']
            if st['v'] < 0.2 and math.hypot(st['x'] - pl['x'], st['z'] - pl['z']) < 0.5: slope_still.append(tid + suf)
    slope_base = base.get('slope_standing')
    # The original OLD calibration included the aborted f006_A forward run.
    # Correcting that single original reference removes one false rolling case:
    # OLD 42/47 -> 41/46. Retain the archived baseline and tighten the current
    # bound only when the hash-guarded replacement is actually applied.
    clean_f006 = any(r.get('id') == 'fence_f006_A' and
                     abs(r.get('settled',{}).get('v',999)) < .2 for r in O.values())
    slope_limit = slope_base - 1 if slope_base is not None and clean_f006 else slope_base
    ok_slope = slope_limit is None or len(slope_still) < slope_limit
    # (5) забор с лица наискось вперёд (09.10, агент физики): пробы, где машина PS2 на газу касается забора с лица под углом и едет
    # вдоль него (разворот 19–26°, 2,6–6,1 м/с) — у порта не «PS2 пускает, порт нет» (прежнее трение кузова о забор 0,2 — вставала)
    glance_ids = [('teleport000_Af', 'разгон вперёд'), ('fence_f007_Af', 'разгон вперёд'), ('fence_f001_Bf', 'разгон вперёд')]
    glance_bad = [t for t in glance_ids if rowmap.get(t, {}).get('verdict') == 'PS2 пускает, порт нет']
    # (6) авто-возврат (аудит п. 17, F9-5 lawn010): за покой после постановки машина порта не уносится через карту (> 50 м), где машина
    # PS2 осталась рядом (< 50 м); прежнее правило «на днище 2 с — в спавн» уносило на 386 м (-DCAR_BELLY_HOME_OLD=1)
    jump_bad, jump_policy = [], []
    for tid, r in sorted(O.items()):
        for k, suf in (('settled', 'f'), ('settled2', 'r')):
            s = r.get(k); g = Pm.get(tid + suf); P0 = r.get('P')
            if not s or not g or 'settled' not in g or not P0: continue
            dp = math.hypot(g['settled']['x'] - g['placed']['x'], g['settled']['z'] - g['placed']['z'])
            do = math.hypot(s['pos'][0] - P0[0], s['pos'][2] - P0[2]) if k == 'settled' else 0.0
            if dp > 50.0 and do < 50.0:
                # Rob's accepted339 rule requires DEATH above the tyre yard.
                # Recognize only the three historical tyre placements, only
                # when the real gameDeath call returned R6D01 during settling,
                # and the first sample agrees with its unchanged XZ apex.
                # carPlace grounds Y, so raw locator Y is not the settled Y.
                apex=g.get('settle_death_apex');trace=g.get('trace',[])
                policy=(os.environ.get('PLACEMENT_POLICY_OLD')!='1' and
                        tid+suf in ('ramp018_Af','ramp018_Bf','ramp018_Br') and
                        g.get('settle_death_zone',-1)>=0 and 0<g.get('settle_death_frame',999)<=6 and apex and trace and
                        g.get('settle_death_name')=='R6D01' and
                        math.hypot(trace[0][1]-apex[0],trace[0][3]-apex[2])<.2)
                (jump_policy if policy else jump_bad).append((tid+suf,round(dp,1)))
    ok = cur <= was and not new and not fails and len(fam) > 0 and len(hed) > 0 and not hfail and ok_slope and not glance_bad and not jump_bad
    res = dict(ok=ok, time=C.clock(), cflags=cflags, points=len(common), mismatch_was=was, mismatch_now=cur, new=new,
               by_point=summ['by_point'], back_family=fam, back_fail=fails, hedge_headon=hed, hedge_fail=hfail, port=summ['port'], slope_total=slope_tot, slope_standing=slope_still,
               slope_base=slope_base,slope_limit=slope_limit, glance_bad=glance_bad, jump_bad=jump_bad,
               jump_policy=jump_policy,policy='Rob339R6airDeath: exact3placements, verified actual zone/apex')
    out = PL.out_dir(level) / 'families'; out.mkdir(parents=True, exist_ok=True)
    (out / f'gate_{tag}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{'PASS' if ok else 'FAIL'} стены по PS2{' [' + cflags + ']' if cflags else ''}: точек {len(common)}, расходится было {was} → стало {cur}, "
          f"новых {len(new)}{(' (' + ', '.join(new[:8]) + ')') if new else ''}; забор с изнанки: проб {len(fam)}, порт не выехал {len(fails)}"
          + (' (' + ', '.join(f"{q['trial']}/seg{q['seg']} {q['port_end']}" for q in fails[:6]) + ')' if fails else '')
          + f"; изгородь в лоб: проб {len(hed)}, порт не встал как PS2 {len(hfail)}"
          + (' (' + ', '.join(f"{q['trial']}/seg{q['seg']} PS2 {q['ps2_end']} порт {q['port_end']}" for q in hfail[:6]) + ')' if hfail else ''))
    print(f"  авто-возврат через карту (> 50 м): {len(jump_bad)}" + (' (' + ', '.join(f'{t} {d} м' for t, d in jump_bad[:6]) + ')' if jump_bad else ''))
    print(f"  принятые DEATH339 R6: {len(jump_policy)}; slope archive/current limit {slope_base}/{slope_limit}")
    print(f"  забор наискось вперёд: проб {len(glance_ids)}, порт встал {len(glance_bad)}" + (' (' + ', '.join(t[0] for t in glance_bad) + ')' if glance_bad else ''))
    print(f"  склон: PS2 катится после постановки {slope_tot}, порт стоит {len(slope_still)} (база {slope_base}){'' if ok_slope else ' — НЕ МЕНЬШЕ БАЗЫ'}")
    print('  по точкам: ' + ', '.join(f'{k} {v}' for k, v in summ['by_point'].items()))
    return 0 if ok else 1


def write_base(level, cflags):
    """база гейта — код ДО правки (cflags прежнего поведения), пишется один раз в tests/walls/ps2_placement_base.json"""
    PT, rows, summ, Pm = run_side(level, 'base', cflags)
    f = C.WT / 'tests/walls/ps2_placement_base.json'; f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dict(time=C.clock(), cflags=cflags, orig_sha=PL.orig_sha(level), port=summ['port'], by_point=summ['by_point'],
                                 points={q['id']: q['cat'] for q in PT}), ensure_ascii=False, indent=1))
    print(f'база: {f.relative_to(C.WT)} — ' + ', '.join(f'{k} {v}' for k, v in summ['by_point'].items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--port', default='port.jsonl'); ap.add_argument('--out', default=None)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--cflags', default=''); ap.add_argument('--write-base', action='store_true')
    ap.add_argument('--trials', default='trials.tsv'); ap.add_argument('--tag', default='now')
    a = ap.parse_args()
    if a.write_base: write_base(a.level, a.cflags); return 0
    if a.gate: return gate(a.level, a.cflags)
    res, summ = analyse(a.level, a.port, a.trials, a.out, a.tag)
    for fam, v in sorted(summ.items(), key=lambda kv: -sum(len(x) for x in kv[1].values())):
        print(f"{dict(FAMILIES)[fam]:70s} " + '  '.join(f'{k}: {len(x)}' for k, x in v.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
