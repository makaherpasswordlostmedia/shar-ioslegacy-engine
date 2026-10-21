#!/usr/bin/env python3
"""Близнецы · маршрут по дорогам L1 для обеих сторон: граф дорог ботов (build/sandbox/roads-l1.bin, оси порта) → A* между точками
AddTeleportDest уровня → ломаная, перевод в оси оригинала (z = −z порта).

  python3 tools/twins/route.py recipe --speed 25 --out tools/twins/recipes/tw_b2_drive.json
Оригинал едет «ведомым телепортом»: каждые 2 кадра тело машины (car_cm) ставится на следующую точку ломаной в 0,6 м над дорогой
и скорость (car_vel) — вдоль дороги. Зоны оригинал грузит сам по пути, как при обычной езде (прыжок через полкарты зоны не грузит:
прогон tw_b2_hops 01.10 — машина на пустой плоскости). Остановки «hops» в рецепте — для разбивки чтений по местам."""
import argparse, heapq, json, math, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

DESTS = [("Simpsons' House", 220, 3.5, -172), ("Kwik E Mart", 209, 3.6, -285), ("Church", 193.8, -0.9, -570),
         ("Springfield Elementary", -11, 0.7, -586), ("Burns' Mansion", -186, 3.5, -96), ("Stonecutters Tunnel", -405, 2, 60),
         ("Power Plant Parking Lot", 40, 0, 296), ("Tomacco", 190, -0.7, 425), ("Trailer Park", 391, -2.2, 494),
         ("Cletus' House", 333.5, -1.8, 356), ("Graveyard", 368, 5.1, 5.4), ("Simpsons' House", 220, 3.5, -172)]   # оси оригинала, scripts level.mfk


LINK = 20.0


def graph(path=None, link=None):
    b = Path(path or C.DATA / 'build/sandbox/roads-l1.bin').read_bytes()
    segs = [struct.unpack_from('<7f', b, i * 28) for i in range(len(b) // 28)]
    nodes, adj = [], {}

    def nid(x, y, z):
        for i, (a, b_, c) in enumerate(nodes):
            if abs(a - x) < 1.5 and abs(c - z) < 1.5 and abs(b_ - y) < 2: return i
        nodes.append((x, y, z)); return len(nodes) - 1
    for ax, ay, az, bx, by, bz, hw in segs:
        i, j = nid(ax, ay, az), nid(bx, by, bz); w = math.dist((ax, az), (bx, bz))
        adj.setdefault(i, []).append((j, w)); adj.setdefault(j, []).append((i, w))
    # отрезки дорог в данных рвутся на перекрёстках (разрывы до ~20 м, 79 компонент без связок): связка между концами ближе LINK м
    # по земле и 2 м по высоте, вес ×3 — маршрут идёт по связкам только там, где дороги нет
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b_ = nodes[i], nodes[j]; d = math.dist((a[0], a[2]), (b_[0], b_[2]))
            if d < (link or LINK) and abs(a[1] - b_[1]) < 2:
                adj.setdefault(i, []).append((j, d * 3)); adj.setdefault(j, []).append((i, d * 3))
    return nodes, adj


def nearest(nodes, x, z):
    return min(range(len(nodes)), key=lambda i: (nodes[i][0] - x) ** 2 + (nodes[i][2] - z) ** 2)


def astar(nodes, adj, s, t):
    h = lambda i: math.dist((nodes[i][0], nodes[i][2]), (nodes[t][0], nodes[t][2]))
    q = [(h(s), 0.0, s, -1)]; came = {}; g = {s: 0.0}
    while q:
        f, d, u, p = heapq.heappop(q)
        if u in came: continue
        came[u] = p
        if u == t: break
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < g.get(v, 1e18): g[v] = nd; heapq.heappush(q, (nd + h(v), nd, v, u))
    if t not in came: return None
    path = [t]
    while came[path[-1]] != -1: path.append(came[path[-1]])
    return path[::-1]


_G = {}


def g_for(link):
    if link not in _G: _G[link] = graph(link=link)
    return _G[link]


def route():
    """по каждому отрезку пути — сначала граф со связками до 12 м (меньше срезок через дворы), дальше 20 и 30 м, пока путь не короче 2,5 прямых"""
    pts, marks = [], []
    for k in range(len(DESTS) - 1):
        a, b = DESTS[k], DESTS[k + 1]
        straight = math.dist((a[1], a[3]), (b[1], b[3]))
        for link in (12.0, 20.0, 30.0):   # путь длиннее 2,5 прямых — объезд через полкарты из-за разрыва в данных дорог: связки длиннее
            nodes, adj = g_for(link)
            s, t = nearest(nodes, a[1], -a[3]), nearest(nodes, b[1], -b[3])
            p = astar(nodes, adj, s, t)
            if p and sum(math.dist((nodes[i][0], nodes[i][2]), (nodes[j][0], nodes[j][2])) for i, j in zip(p, p[1:])) <= 2.5 * straight: break
        if not p: raise SystemExit(f'нет пути по дорогам {a[0]} → {b[0]}')
        print(f'  {a[0]} → {b[0]}: связки до {link:.0f} м, узлов {len(p)}')
        marks.append((len(pts), b[0]))
        pts += [nodes[i] for i in (p if not pts else p[1:])]
    return [(x, y, -z) for x, y, z in pts], marks   # оси оригинала


def resample(pts, step):
    out = [pts[0]]; idx = [0]
    for i in range(1, len(pts)):
        a, b = out[-1], pts[i]; d = math.dist((a[0], a[2]), (b[0], b[2]))
        while d >= step:
            t = step / d; a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t); out.append(a); idx.append(i)
            d = math.dist((a[0], a[2]), (b[0], b[2]))
    return out, idx


def recipe(speed, out_path, start=150, every=2, lift=0.6):
    pts, marks = route()
    step = speed * every / 50.0
    rs, idx = resample(pts, step)
    st = 'build/ps2ref/state_l1_incar.p2s'; W = []; hops = [dict(name="Simpsons' House (старт)", at=start, pos=list(rs[0]))]
    mark_i = {m[0]: m[1] for m in marks[1:]}
    for k in range(len(rs) - 1):
        at = start + k * every; (x, y, z), (x2, _, z2) = rs[k], rs[k + 1]
        d = math.dist((x, z), (x2, z2)) or 1; vx, vz = (x2 - x) / d * speed, (z2 - z) / d * speed
        W += [dict(name='car_cm[0]', value=round(x, 3), at=at, hold=1), dict(name='car_cm[1]', value=round(y + lift, 3), at=at, hold=1),
              dict(name='car_cm[2]', value=round(z, 3), at=at, hold=1),
              dict(name='car_vel[0]', value=round(vx, 3), at=at, hold=1), dict(name='car_vel[1]', value=0.0, at=at, hold=1),
              dict(name='car_vel[2]', value=round(vz, 3), at=at, hold=1)]
        for i in range(idx[k], idx[k + 1] + 1 if k + 1 < len(idx) else idx[k] + 1):
            if i in mark_i: hops.append(dict(name=mark_i.pop(i), at=at, pos=[round(x, 1), round(y, 1), round(z, 1)]))
    frames = start + len(rs) * every + 100
    r = dict(id=Path(out_path).stem, profile=C.PROFILE, state=st, state_sha256=C.sha256(C.DATA / st), frames=frames, every=10,
             trace=['mat[12]', 'mat[13]', 'mat[14]'], writes=W, shots=[h['at'] + 60 for h in hops[1:]], hops=hops,
             route=dict(points=len(rs), meters=round(sum(math.dist((a[0], a[2]), (b[0], b[2])) for a, b in zip(rs, rs[1:]))), speed=speed))
    Path(out_path).write_text(json.dumps(r, ensure_ascii=False))
    print(f"маршрут {r['route']['meters']} м, точек {len(rs)}, кадров {frames} ({frames / 50:.0f} с игры), остановок {len(hops)}, записей {len(W)} → {out_path}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['recipe']); ap.add_argument('--speed', type=float, default=25); ap.add_argument('--out', required=True); ap.add_argument('--lift', type=float, default=0.6)
    a = ap.parse_args(); recipe(a.speed, a.out, lift=a.lift)


# ---- маршрут по сети дорог оригинала (перекрёстки и дороги с полосами из данных диска: tools/traffic_export.py road_network) ----
def road_graph(level=1):
    import importlib.util, numpy as np
    spec = importlib.util.spec_from_file_location('traffic_export', C.DATA / 'tools/traffic_export.py'); te = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(C.DATA / 'tools')); spec.loader.exec_module(te)
    junc, roads = te.road_network(level)
    adj = {}
    for i, r in enumerate(roads):
        if r.get('shortcut'): continue          # срезки ИИ (дворы, тропинки) — не дорога
        L = np.asarray(r['pts'])                # полосы × точки × (x, y, z, путь) — оси порта
        center = L[:, :, :3].mean(axis=0)
        w = float(np.sum(np.linalg.norm(np.diff(center[:, [0, 2]], axis=0), axis=1)))
        poly = [(float(p[0]), float(p[1]), -float(p[2])) for p in center]    # оси оригинала
        adj.setdefault(r['s'], []).append((r['e'], w, poly)); adj.setdefault(r['e'], []).append((r['s'], w, poly[::-1]))
    jpos = [(j['pos'][0], j['pos'][1], -j['pos'][2]) for j in junc]
    return jpos, adj


def route_roads(dests=None, level=1):
    """ломаная по дорогам через точки dests (оси оригинала): ближайший перекрёсток к каждой точке, Дейкстра по длинам дорог"""
    jpos, adj = road_graph(level); dests = dests or DESTS

    def near(x, z): return min(range(len(jpos)), key=lambda k: (jpos[k][0] - x) ** 2 + (jpos[k][2] - z) ** 2)

    pts, marks = [], []
    for k in range(len(dests) - 1):
        s, t = near(dests[k][1], dests[k][3]), near(dests[k + 1][1], dests[k + 1][3])
        dist = {s: 0.0}; prev = {}; q = [(0.0, s)]
        while q:
            d, u = heapq.heappop(q)
            if u == t: break
            if d > dist.get(u, 1e18): continue
            for v, w, poly in adj.get(u, []):
                if d + w < dist.get(v, 1e18): dist[v] = d + w; prev[v] = (u, poly); heapq.heappush(q, (d + w, v))
        if t not in dist: raise SystemExit(f'нет дороги {dests[k][0]} → {dests[k + 1][0]}')
        seg = []; v = t
        while v != s: u, poly = prev[v]; seg = list(poly) + seg[1:] if seg else list(poly); v = u
        marks.append((len(pts), dests[k + 1][0])); pts += seg if not pts else seg[1:]
        print(f'  {dests[k][0]} → {dests[k + 1][0]}: {dist[t]:.0f} м по дорогам')
    return pts, marks
