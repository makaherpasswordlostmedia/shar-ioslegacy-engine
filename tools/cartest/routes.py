#!/usr/bin/env python3
"""Цели маршрутов уровня из данных игры (пункт 9 docs/handoff/LOOP_TERMINAL.md): трамплины и крыши, ни одной
координаты руками. Только чтение: диск Роба (hit-and-run-web/source/game), build/level.shr (COL1, PRP2), дороги.

  python3 tools/cartest/routes.py [--level build/level.shr] [--roads build/sandbox/roads-l1.bin]
  -> build/sandbox/routes-l1.json + build/sandbox/routes-l1.png

Трамплин = зона jumpzone* (jumps.p3d, event 48) или стекло Krusty (PRP1, обломок 19) без зоны рядом. Направление прыжка:
нормаль стекла, если стекло в 25 м; иначе подъём ближайшего наклонного ящика с проходимым верхом в 20 м (лестница
пожарной машины и т.п.); иначе тонкая горизонтальная ось объёма зоны, знак — сторона с обрывом сразу за кромкой. Кромка — высшая опора по линии прыжка в ±8 м. Подъезд — назад от кромки по опоре без ступеней выше 1 м, до
40 м или до дороги. Приземление на 40–120 км/ч — баллистика от кромки под углом склона (без буста: в данных его силы
нет, docs/gameplay.md §14) до первой опоры под траекторией или до стены. Опора — «крыша», если под ней на 3 м и ниже
есть ещё опора. Крыши — связные участки таких опор (сетка 2 м), соседи в 15 м: зазор и перепад. Камеры прыжков
(локаторы с «jump» в имени) привязаны к ближайшему трамплину в 60 м.
"""
import argparse
import ctypes
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / 'hit-and-run-web/source/game'
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string  # noqa: E402  (MIT)

SPEEDS = (40, 60, 80, 100, 120)
GRAV = 9.81


class Col:
    def __init__(self, level):
        lib = ROOT / 'build/tmp/libcolpy.dylib'
        src = [ROOT / 'tools/cartest/colpy.c', ROOT / 'viewer/col.c', ROOT / 'viewer/col.h']
        if not lib.exists() or any(p.stat().st_mtime > lib.stat().st_mtime for p in src):
            lib.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['cc', '-O2', '-shared', '-fPIC', '-I', str(ROOT / 'viewer'), str(src[0]), str(src[1]), '-o', str(lib)], check=True)
        self.L = ctypes.CDLL(str(lib))
        self.L.cp_load.argtypes = [ctypes.c_char_p]
        self.L.cp_ground.argtypes = [ctypes.c_float] * 4 + [ctypes.POINTER(ctypes.c_float)] * 2 + [ctypes.POINTER(ctypes.c_int)]
        self.L.cp_probe.argtypes = [ctypes.c_float] * 4; self.L.cp_probe.restype = ctypes.c_float
        if self.L.cp_load(str(level).encode()):
            raise SystemExit('COL1 не загрузилась: ' + str(level))
        self.y = ctypes.c_float(); self.n = (ctypes.c_float * 3)(); self.m = ctypes.c_int()

    def ground(self, x, z, top=500.0, bot=-1e6):
        """-> (y, ny, материал) самой высокой опоры в [bot, top] или None"""
        if not self.L.cp_ground(x, z, top, bot, ctypes.byref(self.y), self.n, ctypes.byref(self.m)):
            return None
        return self.y.value, self.n[1], self.m.value

    def layers(self, x, z, top=500.0, maxn=6):
        out, t = [], top
        for _ in range(maxn):
            g = self.ground(x, z, t)
            if not g:
                break
            out.append(g[0]); t = g[0] - 0.5
        return out

    def probe(self, x, y, z, h):
        return self.L.cp_probe(x, y, z, h)


def locators(path, want):
    out = []
    for c in walk(read(path)):
        if c.id != 0x3000005:
            continue
        name, p = string(c.data)
        kind, length = struct.unpack_from('<II', c.data, p)
        payload = c.data[p + 8:p + 8 + length * 4]
        pos = list(struct.unpack_from('<3f', c.data, p + 8 + length * 4)); pos[2] *= -1
        ev = struct.unpack_from('<I', payload)[0] if kind == 0 and len(payload) >= 4 else None
        vols = []
        for ch in c.children:
            if ch.id == 0x3000006:
                vn, q = string(ch.data); isrect, = struct.unpack_from('<I', ch.data, q)
                he = struct.unpack_from('<3f', ch.data, q + 4); M = struct.unpack_from('<16f', ch.data, q + 16)
                axes = [(M[0], M[1], -M[2]), (M[4], M[5], -M[6]), (M[8], M[9], -M[10])]
                vols.append(dict(he=he, axes=axes, c=(M[12], M[13], -M[14])))
        if want(name, kind, ev):
            out.append(dict(name=name, kind=kind, event=ev, pos=pos, vols=vols, source=str(path.relative_to(G))))
    return out


def glass_panes(level):
    b = level.read_bytes()
    po = struct.unpack_from('<I', b, 96)[0]
    magic = b[po:po + 4]
    npiece, ntype, ninst, vB, iB = struct.unpack_from('<5I', b, po + 4)
    head = 64 if magic == b'PRP2' else 32
    body = po + head
    types_off = body + vB + iB + 40 * npiece
    inst_off = types_off + 20 * ntype
    brk = [0xFF] * ntype
    if magic == b'PRP2':
        t_off, t_n = struct.unpack_from('<2I', b, po + 44)
        if t_off:
            for t in range(min(t_n, ntype)):
                brk[t] = b[po + t_off + 2 * t + 1]
    out = []
    for i in range(ninst):
        x, y, z, w, qx, qy, qz, ty = struct.unpack_from('<3f4fI', b, inst_off + 32 * i)
        if ty < ntype and brk[ty] == 19:
            nx, nz = 2 * (qx * qz + w * qy), 1 - 2 * (qx * qx + qy * qy); l = math.hypot(nx, nz)
            out.append(dict(inst=i, type=ty, x=x, y=y, z=z, n=(nx / l, nz / l)))
    return out


def ramp_boxes(level):
    """наклонные ящики COL1 с проходимым верхом (подъём 10–50°, длина по подъёму от 4 м): лестницы, пандусы.
    -> [(центр xyz, направление вверх по подъёму (dx, dz), подъём °, длина)]"""
    b = level.read_bytes(); co = struct.unpack_from('<I', b, 92)[0]
    _, ox, oz, cell, W, H, ntri, nbox, ncyl, nseg, nref, flags = struct.unpack_from('<4s3f8I', b, co)
    bx = np.frombuffer(b, np.float32, count=nbox * 16, offset=co + 48 + ntri * 48).reshape(nbox, 16)
    out = []
    for r in bx:
        A = [r[3:6], r[6:9], r[9:12]]; h = r[12:15]
        k = int(np.argmax([abs(a[1]) for a in A])); n = A[k] * np.sign(A[k][1])
        if not (math.cos(math.radians(50)) < n[1] < math.cos(math.radians(10))):
            continue
        hz = np.array([n[0], n[2]]); hz /= np.linalg.norm(hz)
        j = max((j for j in range(3) if j != k), key=lambda j: abs(A[j][0] * hz[0] + A[j][2] * hz[1]))
        if 2 * h[j] < 4:
            continue
        out.append(((float(r[0]), float(r[1]), float(r[2])), (float(-hz[0]), float(-hz[1])), math.degrees(math.acos(n[1])), float(2 * h[j])))
    return out


def ramp_line(col, cx, cz, d, cy, back=10.0):
    """кромка, угол, подъезд по линии d через (cx, cz). Кромка — ход по опоре вперёд от −10 м до +30 м (ступени
    не выше 1 м): последняя точка перед обрывом больше 1 м; нет обрыва — высшая точка хода"""
    dx, dz = d
    g = col.ground(cx - dx * back, cz - dz * back, cy + 8, cy - 12) or col.ground(cx - dx * back, cz - dz * back, cy + 8)
    if not g:
        g = col.ground(cx, cz, cy + 8) or col.ground(cx, cz)
        if not g:
            return None
        s0 = 0.0
    else:
        s0 = -back
    prev, lip, top = g[0], None, (s0, g[0])
    for s in np.arange(s0 + 0.5, 30.01, 0.5):
        h = col.ground(cx + dx * s, cz + dz * s, prev + 1.0, prev - 1.0)
        if not h or h[1] <= 0.5:
            lip = (s - 0.5, prev); break
        prev = h[0]
        if prev > top[1]:
            top = (s, prev)
    ls, ly = lip if lip else top
    lx, lz = cx + dx * ls, cz + dz * ls
    gb = col.ground(lx - dx * 2, lz - dz * 2, ly + 1, ly - 6)
    ang = math.atan2(ly - gb[0], 2.0) if gb else 0.0
    run, prev = 0.0, ly
    for s in np.arange(1.0, 40.01, 1.0):              # назад от кромки: вперёд машина едет отсюда к prev, значит
        h = col.ground(lx - dx * s, lz - dz * s, prev + 3.0, prev - 0.6)   # ступень вверх больше 0.6 м — стена
        if not h or h[1] <= 0.5:
            break
        run, prev = s, h[0]
    return dict(lip=[round(lx, 2), round(ly, 2), round(lz, 2)], angleDeg=round(math.degrees(ang), 1), runUpM=run,
                start=[round(lx - dx * run, 2), round(prev, 2), round(lz - dz * run, 2)], lipFound='обрыв' if lip else 'высшая точка')


def landing(col, lip, d, ang, kmh):
    """баллистика от кромки: -> dict(где, xyz, класс)"""
    v = kmh / 3.6; vx, vy = v * math.cos(math.radians(ang)), v * math.sin(math.radians(ang))
    x0, y0, z0 = lip; dx, dz = d; t, dt = 0.0, 0.02
    prev = (x0, y0 + 0.3, z0)
    while t < 6.0:
        t += dt
        s = vx * t; x, z = x0 + dx * s, z0 + dz * s; y = y0 + 0.3 + vy * t - GRAV * t * t / 2
        g = col.ground(x, z, y + 0.05, -1e6)
        up = col.ground(x, z, y + 3.0, y + 0.05)                     # опора над траекторией рядом — стена/крыша сбоку
        if up and up[0] > y + 0.6 and t > 0.15:
            return dict(result='стена', at=[round(x, 1), round(y, 1), round(z, 1)], t=round(t, 2), wallTop=round(up[0], 1))
        if g and y <= g[0] + 0.05:
            lay = col.layers(x, z, g[0] + 0.1)
            roof = len(lay) > 1 and lay[0] - lay[-1] >= 3.0
            return dict(result='крыша' if roof else ('куст' if g[2] == 1 else 'земля'), at=[round(x, 1), round(g[0], 1), round(z, 1)],
                        t=round(t, 2), distM=round(s, 1), dropM=round(y0 - g[0], 1))
        prev = (x, y, z)
    return dict(result='нет опоры 6 с', at=[round(prev[0], 1), round(prev[1], 1), round(prev[2], 1)])


def roofs(col, step=2.0):
    ox, oz, cell, w, h = (ctypes.c_float(), ctypes.c_float(), ctypes.c_float(), ctypes.c_int(), ctypes.c_int())
    col.L.cp_grid(ctypes.byref(ox), ctypes.byref(oz), ctypes.byref(cell), ctypes.byref(w), ctypes.byref(h))
    x0, z0, W, H = ox.value, oz.value, w.value * cell.value, h.value * cell.value
    nx, nz = int(W / step), int(H / step)
    top = np.full((nz, nx), np.nan, np.float32); low = np.full((nz, nx), np.nan, np.float32)
    for j in range(nz):
        for i in range(nx):
            lay = col.layers(x0 + (i + .5) * step, z0 + (j + .5) * step)
            if len(lay) > 1 and lay[0] - lay[-1] >= 3.0:
                top[j, i], low[j, i] = lay[0], lay[-1]
    lab = np.zeros((nz, nx), np.int32); n = 0; patches = []
    for j in range(nz):
        for i in range(nx):
            if np.isnan(top[j, i]) or lab[j, i]:
                continue
            n += 1; stack = [(j, i)]; lab[j, i] = n; cells = []
            while stack:
                a, c = stack.pop(); cells.append((a, c))
                for da, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    b, e = a + da, c + dc
                    if 0 <= b < nz and 0 <= e < nx and not lab[b, e] and not np.isnan(top[b, e]) and abs(top[b, e] - top[a, c]) < 1.0:
                        lab[b, e] = n; stack.append((b, e))
            if len(cells) < 4:                                   # меньше 16 м² — не крыша для машины
                continue
            ys = np.array([top[a, c] for a, c in cells]); gs = np.array([low[a, c] for a, c in cells])
            xs = np.array([x0 + (c + .5) * step for a, c in cells]); zs = np.array([z0 + (a + .5) * step for a, c in cells])
            patches.append(dict(id=len(patches), areaM2=len(cells) * step * step, y=round(float(ys.mean()), 1),
                                aboveGroundM=round(float((ys - gs).mean()), 1), x=round(float(xs.mean()), 1), z=round(float(zs.mean()), 1),
                                bbox=[round(float(xs.min()), 1), round(float(zs.min()), 1), round(float(xs.max()), 1), round(float(zs.max()), 1)],
                                _pts=np.c_[xs, zs, ys]))
    for p in patches:
        p['neighbours'] = []
    for a in range(len(patches)):
        for b in range(a + 1, len(patches)):
            A, B = patches[a], patches[b]
            if A['bbox'][0] - 15 > B['bbox'][2] or B['bbox'][0] - 15 > A['bbox'][2] or A['bbox'][1] - 15 > B['bbox'][3] or B['bbox'][1] - 15 > A['bbox'][3]:
                continue
            pa, pb = A['_pts'], B['_pts']
            d2 = ((pa[:, None, :2] - pb[None, :, :2]) ** 2).sum(-1); k = np.unravel_index(np.argmin(d2), d2.shape)
            gap = float(math.sqrt(d2[k]))
            if gap <= 15:
                dy = float(pb[k[1], 2] - pa[k[0], 2])
                A['neighbours'].append(dict(id=B['id'], gapM=round(gap, 1), dyM=round(dy, 1)))
                B['neighbours'].append(dict(id=A['id'], gapM=round(gap, 1), dyM=round(-dy, 1)))
    for p in patches:
        del p['_pts']
    return patches


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=Path, default=ROOT / 'build/level.shr')
    ap.add_argument('--out', type=Path, default=ROOT / 'build/sandbox/routes-l1.json')
    a = ap.parse_args()
    col = Col(a.level)
    zones = locators(G / 'art/missions/level01/jumps.p3d', lambda n, k, e: e == 48)
    cams = []
    for f in sorted((G / 'art').glob('l1*.p3d')):
        try:
            cams += locators(f, lambda n, k, e: 'jump' in n.lower())
        except Exception:
            pass
    glass = glass_panes(a.level)
    rboxes = ramp_boxes(a.level)
    ramps, used, rbk = [], set(), 10.0
    for zn in zones:
        x, y, z = zn['pos']
        near = min(glass, key=lambda g: math.hypot(g['x'] - x, g['z'] - z)) if glass else None
        gd = math.hypot(near['x'] - x, near['z'] - z) if near else 1e9
        if near and gd > 25:                                         # стекло дальше: только если стоит на линии прыжка
            ax_, az_ = near['n']; t_ = (x - near['x']) * ax_ + (z - near['z']) * az_; lat = abs((x - near['x']) * az_ - (z - near['z']) * ax_)
            if -45 <= t_ <= 0 and lat <= 8:
                gd = 25
        if near and gd <= 25:
            d, how = near['n'], 'нормаль стекла #%d' % near['inst']; used.add(near['inst'])
        elif rboxes and min(math.hypot(q[0][0] - x, q[0][2] - z) for q in rboxes) <= 20:
            q = min(rboxes, key=lambda q: math.hypot(q[0][0] - x, q[0][2] - z))
            d, how = q[1], 'подъём наклонного ящика (%.0f°, %.0f м)' % (q[2], q[3]); near = None
            x, y, z = q[0]; rbk = q[3] * math.cos(math.radians(q[2])) / 2 + 2   # ход по опоре — от нижнего конца ящика
        else:
            v = zn['vols'][0] if zn['vols'] else None
            if v:
                hor = [(v['he'][k], v['axes'][k]) for k in range(3) if abs(v['axes'][k][1]) < 0.5]
                ax = min(hor)[1] if hor else (1, 0, 0)
            else:
                ax = (1, 0, 0)
            l = math.hypot(ax[0], ax[2]); d0 = (ax[0] / l, ax[2] / l)
            def drop(dd):                                            # обрыв сразу за кромкой по этой стороне
                g0 = col.ground(x, z, y + 8, y - 12); best = 0.0
                for s in (2, 3, 4, 5, 6):
                    g = col.ground(x + dd[0] * s, z + dd[1] * s, (g0[0] if g0 else y) + 1, -1e6)
                    if g0 and (not g or g0[0] - g[0] > best):
                        best = g0[0] - (g[0] if g else g0[0] - 30)
                return best
            d = d0 if drop(d0) >= drop((-d0[0], -d0[1])) else (-d0[0], -d0[1])
            how = 'тонкая ось зоны, сторона обрыва'
            near = None
        ramps.append(dict(name=zn['name'], source=zn['source'], zone=[round(v, 1) for v in zn['pos']], direction=[round(d[0], 3), round(d[1], 3)],
                          directionFrom=how, glass=near['inst'] if near and gd <= 25 else None, _c=(x, y, z), _back=rbk if 'ящика' in how else 10.0))
        rbk = 10.0
    rep_boxes = len(rboxes)
    for g in glass:
        if g['inst'] in used:
            continue
        ramps.append(dict(name='glass%d' % g['inst'], source='level.shr PRP2', zone=None, direction=[round(g['n'][0], 3), round(g['n'][1], 3)],
                          directionFrom='нормаль стекла #%d' % g['inst'], glass=g['inst'], _c=(g['x'], g['y'] - 2.0, g['z'] - 0.0)))
    for r in ramps:
        cx, cy, cz = r.pop('_c'); d = tuple(r['direction']); back = r.pop('_back', 10.0)
        if r['zone'] is None:                                        # от стекла: кромка чуть до плоскости стекла
            cx, cz = cx - d[0] * 3, cz - d[1] * 3
        line = ramp_line(col, cx, cz, d, cy, back)
        if not line:
            r['error'] = 'нет опоры у зоны'; continue
        r.update(line)
        r['landing'] = {str(k): landing(col, r['lip'], d, max(0.0, r['angleDeg']), k) for k in SPEEDS}
        if r['glass'] is not None:
            g = next(q for q in glass if q['inst'] == r['glass'])
            r['glassXYZ'] = [round(g['x'], 1), round(g['y'], 1), round(g['z'], 1)]
        cam = min(cams, key=lambda c: math.hypot(c['pos'][0] - r['lip'][0], c['pos'][2] - r['lip'][2])) if cams else None
        if cam and math.hypot(cam['pos'][0] - r['lip'][0], cam['pos'][2] - r['lip'][2]) <= 60:
            r['camera'] = dict(name=cam['name'], pos=[round(v, 1) for v in cam['pos']])
    patches = roofs(col)
    for r in ramps:
        for k, L in r.get('landing', {}).items():
            if L['result'] == 'крыша':
                x, z = L['at'][0], L['at'][2]
                p = next((p for p in patches if p['bbox'][0] - 2 <= x <= p['bbox'][2] + 2 and p['bbox'][1] - 2 <= z <= p['bbox'][3] + 2), None)
                if p:
                    L['roof'] = p['id']
    rep = dict(kind='routes-v1', level=str(a.level.relative_to(ROOT)), speedsKmh=list(SPEEDS), ramps=ramps, roofs=patches,
               counts=dict(jumpzones=len(zones), glass=len(glass), glassWithRamp=sum(1 for r in ramps if r['glass'] is not None),
                           cameras=len(cams), roofs=len(patches), rampBoxes=rep_boxes),
               note='из данных; приземление — баллистика от кромки без буста, проверка ездой — пункт 10')
    tmp = a.out.with_suffix('.json.tmp'); tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1)); tmp.replace(a.out)
    with open(a.out.with_suffix('.tsv'), 'w') as f:                  # вход раннера ботов tools/cartest/routes_run.c
        for r in ramps:
            if 'lip' in r:
                f.write('%s\t%.3f %.3f %.3f\t%.4f %.4f\t%.3f %.3f %.3f\t%d\n' % (r['name'], *r['start'], *r['direction'], *r['lip'],
                        r['glass'] if r['glass'] is not None else -1))
    draw(col, rep, a.out.with_suffix('.png'))
    print('трамплинов %d (зон %d, стёкол %d, со стеклом %d), камер %d, крыш %d' % (len(ramps), len(zones), len(glass),
          rep['counts']['glassWithRamp'], len(cams), len(patches)))
    print('маршруты: %s, карта: %s' % (a.out.relative_to(ROOT), a.out.with_suffix('.png').relative_to(ROOT)))


def draw(col, rep, png):
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / 'tools'))
    from col_check import load, parse_col
    b, L = load(str(ROOT / rep['level'])); C = parse_col(b, L['col'])
    x0, z0 = C['ox'], C['oz']; W, H = int(C['W'] * C['cell']), int(C['H'] * C['cell'])
    img = Image.new('RGB', (W, H), (15, 15, 18)); d = ImageDraw.Draw(img); P = lambda x, z: (x - x0, z - z0)
    T = C['tri']; ys = T[:, :3, 1].mean(1); lo, hi = np.percentile(ys, 2), np.percentile(ys, 98)
    for t, y in zip(T, ys):
        g = int(35 + 90 * np.clip((y - lo) / (hi - lo), 0, 1)); d.polygon([P(t[k, 0], t[k, 2]) for k in range(3)], fill=(g, g, g))
    for p in rep['roofs']:
        x1, z1, x2, z2 = p['bbox']; d.rectangle([P(x1, z1), P(x2, z2)], outline=(80, 160, 255))
    col_ = {'земля': (80, 220, 80), 'крыша': (80, 160, 255), 'куст': (40, 170, 90), 'стена': (255, 60, 60)}
    for r in rep['ramps']:
        if 'lip' not in r:
            continue
        lx, _, lz = r['lip']; sx, _, sz = r['start']
        d.line([P(sx, sz), P(lx, lz)], fill=(255, 210, 40), width=2)
        for k, Lr in r['landing'].items():
            x, _, z = Lr['at']; u, v = P(x, z); c = col_.get(Lr['result'], (200, 200, 200))
            d.ellipse([u - 2, v - 2, u + 2, v + 2], fill=c); d.line([P(lx, lz), (u, v)], fill=c)
        d.text((P(lx, lz)[0] + 4, P(lx, lz)[1] - 10), r['name'].replace('jumpzone', 'j'), fill=(255, 255, 255))
    img.save(png)


if __name__ == '__main__':
    main()
