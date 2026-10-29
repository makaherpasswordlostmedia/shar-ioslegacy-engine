#!/usr/bin/env python3
"""Камеры комнат (пункт 11.2): независимый разбор диска против того, что считает движок (tests/rooms/cams_host.c через
viewer/roomcam.c по пакету build/interiors-l1-gfx.bin). Свой разбор чанков — не общий с экспортом (tools/interior_export.py):
локатор 0x3000005 вида 12 (StaticCam: TargetPosition 3f, FOV, TargetLag, FollowPlayer, TransitionTargetRate, Flags,
CutInOut, Data) и вида 4 (Spline 0x3000007 -> RailCam 0x300000A: Behaviour, MinRadius, MaxRadius, TrackRail, TrackDist,
ReverseSense, FOV, TargetOffset 3f, AxisPlay 3f, PositionLag, TargetLag), TriggerVolume 0x3000006 (isRect, полуоси, матрица).
Для центра каждого триггера каждой камеры сверяются: какая камера выбрана (первая по порядку файла, в чьём триггере точка),
её FOV по вертикали, глаз и точка взгляда (толкование полей — viewer/roomcam.h).
Рельсы (строки RAIL движка, с 29.09): число точек и длина ломаной, последняя точка — как на диске (точек сколько в данных:
Обсерватория уровней 3 и 6 — 13).
  cams_check.py HOST_OUT [--level N]     0 = совпало (PASS); уровень — комнаты l<N>i*.p3d (по умолчанию 1)
  cams_check.py --plant ПАКЕТ КОПИЯ      подложить неверную камеру (Kwik-E-Mart: первая камера сдвинута на 2 м) для красного прогона
  cams_check.py --plant-rail9 ПАКЕТ КОПИЯ  рельс длиннее 9 точек обрезан до 9 (как предел до 29.09) — обязан дать FAIL"""
import sys, struct, math, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ART = (ROOT / 'hit-and-run-web/source/game/art').resolve()
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string   # MIT, разбор контейнера Pure3D
ROOMS = {'l1i00': 'SpringfieldElementary', 'l1i01': 'KwikEMart', 'l1i02': 'SimpsonsHouse'}
NAMES = {0: 'SpringfieldElementary', 1: 'KwikEMart', 2: 'SimpsonsHouse', 3: 'DMV', 4: 'Moes', 5: 'AndroidsDungeon', 6: 'Observatory',
         7: 'BartRoom'}   # номер файла комнаты -> имя (как tools/interior_export.py NAMES)


def rooms_of(level):
    return {p.stem: NAMES[int(p.stem[3:])] for p in sorted(ART.glob(f'l{level}i*.p3d'))}
TOL = 2e-3


def mz(v): return (v[0], v[1], -v[2])


def trig(c):
    nm, q = string(c.data); rect, = struct.unpack_from('<I', c.data, q); half = struct.unpack_from('<3f', c.data, q + 4)
    m = struct.unpack_from('<16f', c.data, q + 16); axes, hh = [], []
    for r in range(3):
        a = mz(m[4 * r:4 * r + 3]); l = math.sqrt(sum(x * x for x in a)) or 1.0
        axes.append(tuple(x / l for x in a)); hh.append(half[r] * l)
    return dict(rect=rect, c=mz(m[12:15]), half=hh, ax=axes)


def inside(t, p):
    d = [p[i] - t['c'][i] for i in range(3)]
    if not t['rect']: return sum(x * x for x in d) <= t['half'][0] ** 2
    return all(abs(sum(d[i] * t['ax'][k][i] for i in range(3))) <= t['half'][k] for k in range(3))


def cameras(stem):
    cams = []
    for c in walk(read(ART / f'{stem}.p3d')):
        if c.id != 0x3000005: continue
        name, p = string(c.data); kind, ln = struct.unpack_from('<II', c.data, p)
        if kind not in (4, 12): continue
        pay = c.data[p + 8:p + 8 + ln * 4]; pos = mz(struct.unpack_from('<3f', c.data, p + 8 + ln * 4))
        trs = [trig(s) for s in c.children if s.id == 0x3000006]
        if kind == 12:
            t3 = struct.unpack_from('<3f', pay); fov, = struct.unpack_from('<f', pay, 12); follow, = struct.unpack_from('<I', pay, 20)
            cams.append(dict(name=name, type=0, pos=pos, target=mz(t3), fov=fov, follow=follow, trig=trs))
        else:
            sp = next(s for s in c.children if s.id == 0x3000007); _, q = string(sp.data); n, = struct.unpack_from('<I', sp.data, q)
            pts = [mz(struct.unpack_from('<3f', sp.data, q + 4 + 12 * i)) for i in range(n)]
            rc = next(s for s in sp.children if s.id == 0x300000a); _, q = string(rc.data)
            v = struct.unpack_from('<I2fIfIf3f3f2f', rc.data, q)
            cams.append(dict(name=name, type=1, pts=pts, minR=v[1], maxR=v[2], track=v[3], trackDist=v[4], reverse=v[5], fov=v[6], offset=mz(v[7:10]), trig=trs))
    return cams


def rail_pose(c, p):   # поведение Distance (viewer/roomcam.c roomRailParam, камера только включилась)
    P = c['pts']; seg = [math.dist(P[k], P[k + 1]) for k in range(len(P) - 1)]; L = sum(seg)
    def at(t):
        for k, l in enumerate(seg):
            if t <= l or k == len(seg) - 1:
                u = min(max(t / l if l > 1e-6 else 0.0, 0.0), 1.0); return [P[k][i] + (P[k + 1][i] - P[k][i]) * u for i in range(3)]
            t -= l
        return list(P[0])
    best, tc, acc = 1e30, 0.0, 0.0
    for k, l in enumerate(seg):
        a, b = P[k], P[k + 1]; ab = [b[i] - a[i] for i in range(3)]; l2 = sum(x * x for x in ab)
        u = min(max(sum((p[i] - a[i]) * ab[i] for i in range(3)) / l2, 0.0), 1.0) if l2 > 1e-12 else 0.0
        d = sum((a[i] + ab[i] * u - p[i]) ** 2 for i in range(3))
        if d < best: best, tc = d, acc + u * l
        acc += l
    A_, B_ = (seg[0], L - seg[-1]) if len(P) >= 4 else (0.0, L)   # правка 186: только между внутренними точками сплайна
    tc = min(max(tc, A_), B_)
    hd = lambda t: math.hypot(at(t)[0] - p[0], at(t)[2] - p[2])
    def solve(a, b, want):
        fa = hd(a) - want
        for _ in range(24):
            m = (a + b) / 2; fm = hd(m) - want
            if (fm > 0) == (fa > 0): a, fa = m, fm
            else: b = m
        return (a + b) / 2
    end = B_ if c['reverse'] else A_   # правка 186: включилась — на MaxRadius от Гомера назад по рельсу (ReverseSense — вперёд)
    t = tc if hd(tc) >= c['maxR'] else (end if hd(end) <= c['maxR'] else solve(tc, end, c['maxR']))
    # цель (правка 138): TargetOffset в осях рельса в точке t — x вбок (fw × up), y вверх, z данных вдоль рельса
    a, b = at(max(t - .05, 0.0)), at(min(t + .05, L)); fw = [b[0] - a[0], b[2] - a[2]]
    if math.hypot(*fw) < 1e-4: fw = [P[-1][0] - P[0][0], P[-1][2] - P[0][2]]
    if math.hypot(*fw) < 1e-4: fw = [0.0, 1.0]
    n = math.hypot(*fw); fx, fz = fw[0] / n, fw[1] / n; o = c['offset']; oz = -o[2]
    base = p
    if c.get('track'):   # правка 186 (близнец v17_house_cam): TrackRail 1 — от точки рельса на TrackDist отрезков сплайна впереди
        acc, k = 0.0, 0
        while k < len(seg) - 1 and t > acc + seg[k]: acc += seg[k]; k += 1
        U = k + ((t - acc) / seg[k] if seg[k] > 1e-6 else 0.0) + c['trackDist']
        s_ = 0 if U < 0 else (len(seg) - 1 if U >= len(seg) else int(U)); u = U - s_
        base = [P[s_][i] + (P[s_ + 1][i] - P[s_][i]) * u for i in range(3)]
    return at(t), [base[0] + o[0] * -fz + oz * fx, base[1] + o[1], base[2] + o[0] * fx + oz * fz]


def expected():
    out = []
    for stem, room in ROOMS.items():
        cams = cameras(stem)
        for i, c in enumerate(cams):
            for k, t in enumerate(c['trig'][:4]):
                p = t['c']; pick = next((j for j, cc in enumerate(cams) if any(inside(tt, p) for tt in cc['trig'][:4])), -1)
                cc = cams[pick if pick >= 0 else i]
                if cc['type'] == 0: eye = cc['pos']; look = [p[j] + cc['target'][j] for j in range(3)] if cc['follow'] else cc['target']
                else: eye, look = rail_pose(cc, p)
                fovy = 2 * math.degrees(math.atan(math.tan(math.radians(cc['fov']) / 2) * .75))
                out.append((room, i, c['name'], k, pick, fovy, *eye, *look))
    return out


def check(host):
    txt = Path(host).read_text().splitlines()
    got = [l.split() for l in txt if l.startswith('CAM ')]
    exp = expected(); bad = []
    rails = {(l.split()[1], l.split()[3]): l.split() for l in txt if l.startswith('RAIL ')}
    for stem, room in ROOMS.items():
        for c in cameras(stem):
            if c['type'] != 1: continue
            r = rails.get((room, c['name']))
            if r is None: bad.append(f'{room} {c["name"]}: движок не выдал рельс'); continue
            P = c['pts']; L = sum(math.dist(P[k], P[k + 1]) for k in range(len(P) - 1))
            if int(r[4]) != len(P) or abs(float(r[5]) - L) > TOL or max(abs(float(r[6 + i]) - P[-1][i]) for i in range(3)) > TOL:
                bad.append(f'{room} {c["name"]}: рельс в движке {r[4]} точек, длина {float(r[5]):.3f}; на диске {len(P)} точек, длина {L:.3f}')
    if len(got) != len(exp): bad.append(f'строк движка {len(got)}, по диску {len(exp)}')
    for g, e in zip(got, exp):
        room, i, name, k = g[1], int(g[2]), g[3], int(g[5]); pick = int(g[9]); vals = [float(x) for x in g[10:17]]
        if (room, i, name, k) != e[:4]: bad.append(f'порядок: движок {room} {i} {name} {k}, диск {e[:4]}'); continue
        if pick != e[4]: bad.append(f'{room} {name} триггер {k}: движок выбрал камеру {pick}, по диску {e[4]}')
        diff = max(abs(a - b) for a, b in zip(vals, e[5:]))
        if diff > TOL: bad.append(f'{room} {name} триггер {k}: расхождение {diff:.3f} (движок {[round(v, 3) for v in vals]}, диск {[round(v, 3) for v in e[5:]]})')
    return bad, len(exp), sorted({(e[0], e[2]) for e in exp})


def plant(src, dst):
    b = bytearray(Path(src).read_bytes()); n, = struct.unpack_from('<I', b, 4)
    for r in range(n):
        name = b[16 + 48 * r:16 + 48 * r + 32].split(b'\0')[0].decode(); off, = struct.unpack_from('<I', b, 16 + 48 * r + 32)
        if name != 'KwikEMart': continue
        coff, = struct.unpack_from('<I', b, off + 120); x, = struct.unpack_from('<f', b, off + coff + 48)
        struct.pack_into('<f', b, off + coff + 48, x + 2.0)   # первая камера Kwik-E-Mart: позиция на 2 м вбок
    Path(dst).write_bytes(bytes(b))


def plant_rail9(src, dst):
    """Каждый рельс длиннее 9 точек (точки в хвосте таблицы, @504 записи) -> первые 9 точек на месте записи, npts = 9, @504 = 0:
    ровно то, что дал бы предел записи камеры 9 точек (tools/interior_export.py до 29.09)."""
    b = bytearray(Path(src).read_bytes()); n, = struct.unpack_from('<I', b, 4); cut = 0
    for r in range(n):
        off, = struct.unpack_from('<I', b, 16 + 48 * r + 32)
        coff, nc = struct.unpack_from('<2I', b, off + 120)
        for i in range(nc):
            rec = off + coff + 512 * i; kind, npts = struct.unpack_from('<I4xI', b, rec + 32); x, = struct.unpack_from('<I', b, rec + 504)
            if kind != 1 or not x: continue
            b[rec + 384:rec + 384 + 108] = b[off + x:off + x + 108]; struct.pack_into('<I', b, rec + 40, 9); struct.pack_into('<I', b, rec + 504, 0); cut += 1
    Path(dst).write_bytes(bytes(b)); print(f'обрезано до 9 точек рельсов: {cut}')
    return 0 if cut else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('host', nargs='?'); ap.add_argument('--plant', nargs=2, metavar=('ПАКЕТ', 'КОПИЯ'))
    ap.add_argument('--plant-rail9', nargs=2, metavar=('ПАКЕТ', 'КОПИЯ')); ap.add_argument('--level', type=int, default=1)
    a = ap.parse_args()
    global ROOMS
    if a.level != 1: ROOMS = rooms_of(a.level)
    if a.plant: plant(*a.plant); return 0
    if a.plant_rail9: return plant_rail9(*a.plant_rail9)
    bad, n, cams = check(a.host)
    print(f'камер {len(cams)}, проверено точек (центры триггеров) {n}: ' + ', '.join(f'{r}/{c}' for r, c in cams))
    for l in bad[:12]: print('  ПРОВАЛ:', l)
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
