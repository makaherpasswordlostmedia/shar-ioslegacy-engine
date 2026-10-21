#!/usr/bin/env python3
"""Правка Роба 340: «по краям экрана иногда обламывается тень от деревьев на траве — будто учитывается старый узкий экран».
Модель GE на Маке (только чтение build/level.shr, без эмулятора) и проверка настоящего кода среза viewer/ge_guard.h.

  python3 tests/guard340/ge340.py --host НОВЫЙ --host-old ПРЕЖНИЙ [--level build/level.shr] [--camf smoke.txt …]

Модель GE (как железо — кадры TEST 10, правка 325; программная отрисовка безголового эмулятора так же): треугольник режется по
near (GU_CLIP_PLANES), вершина после среза дальше 2048 px от центра экрана — треугольник выброшен целиком.
Позы: пешком у теней деревьев уровня (текстуры «тень дерева» — кусок города, полупрозрачная наклейка на траве): Гомер в центре
скопления тени, 8 курсов, камера пешком (3,6 м сзади, 2,4 м выше ступней, взгляд на 1 м выше, угол 54°), ближняя плоскость
1,5 / 0,5 / 0,28 / 0,25 м (homer.c camNear у стены/дерева/машины — до 0,25); плюс позы CAMF из прогонов эмулятора (--camf).
1) прежнее (-DGG_OLD: ничего не режется): видимая площадь выброшенных треугольников по позам — тени и земля (КРАСНЫЙ должен быть);
2) новое (настоящий ggRisk/ggCut/ggBoxRisk): в кадрах с ближней < 1,5 м — 0 px потерь; веер среза совпадает с идеальным (тот же
   треугольник, срезанный по near без полосы) с точностью 1 px; каждый треугольник под риском лежит в куске и клетке, чей бокс
   ggBoxRisk помечает (иначе движок нарисовал бы его листом/целиком и GE его бы выбросил);
3) при ближней 1,5 м (правило не включается) — остаток для сведения (длинные полосы экспорта, не тени).
ИТОГ зелёный: новое 0 px и 0 промахов бокса, прежнее теряет тени (> 5000 px), площадь веера сходится."""
import argparse, collections, math, re, struct, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import shr7read   # noqa: E402

GB = 2048.; ASPECT = 16 / 9
SHADOW_TEX_MIN_TRIS = 1000   # «тень дерева»: полупрозрачная текстура города, горизонтальные наклейки (уровень 1 — tex 131 и 41)


def level(path):
    L = shr7read.load(path); b = Path(path).read_bytes()
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    L['PBB'] = np.array([struct.unpack_from('<6f', b, ptab + 80 * i) for i in range(npc)])
    L['CBB'] = np.array([struct.unpack_from('<6f', b, ctab + 48 * i) for i in range(ncell)])
    L['C'] = L['P'].mean(1)
    return L


def shadow_tex(L):
    """полупрозрачные текстуры города, лежащие горизонтально (наклейки-тени)"""
    out = []
    for t in np.unique(L['TEX'][(L['FL'] & 2) != 0]):
        m = (L['TEX'] == t) & ((L['FL'] & 2) != 0)
        if m.sum() < SHADOW_TEX_MIN_TRIS: continue
        P = L['P'][m]; n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); hz = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        if (hz > .9).mean() > .95: out.append(int(t))
    return out


def basis(eye, at):
    f = np.asarray(at, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    return r, u, f


def area_on_screen(sx, sy):
    p = list(zip(sx, sy))
    for k, lim, sgn in ((0, 240, 1), (0, 240, -1), (1, 136, 1), (1, 136, -1)):
        q = []
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]; fa, fb = sgn * a[k] - lim, sgn * b[k] - lim
            if fa <= 0: q.append(a)
            if (fa <= 0) != (fb <= 0): t = fa / (fa - fb); q.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        p = q
        if len(p) < 3: return 0.
    x = np.array([v[0] for v in p]); y = np.array([v[1] for v in p])
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2


def clip_near(V, near):
    out = []
    for i in range(len(V)):
        a, b = V[i], V[(i + 1) % len(V)]
        if a[2] >= near: out.append(a)
        if (a[2] >= near) != (b[2] >= near): out.append(a + (b - a) * ((near - a[2]) / (b[2] - a[2])))
    return np.array(out)


def ge(V, near, tvx, tvy, band=True):
    """треугольник/многоугольник в осях камеры -> (видимая площадь px, выброшен ли GE)"""
    poly = clip_near(list(V), near)
    if len(poly) < 3: return 0., False
    sx = poly[:, 0] / poly[:, 2] / tvx * 240; sy = poly[:, 1] / poly[:, 2] / tvy * 136
    a = area_on_screen(sx, sy)
    return a, bool(band and max(np.abs(sx).max(), np.abs(sy).max()) >= GB)


def poses(L, shadow, extra):
    P = []
    m = np.isin(L['TEX'], shadow); C = L['C'][m]
    cells = collections.Counter(map(tuple, (C[:, [0, 2]] // 20).astype(int)))
    for (cx, cz), n in cells.most_common(16):
        pts = C[(C[:, 0] // 20 == cx) & (C[:, 2] // 20 == cz)]; c = pts.mean(0); g = pts[:, 1].min()
        for k in range(8):
            h = k * math.pi / 4 + .2; fw = np.array([math.sin(h), 0, math.cos(h)]); homer = np.array([c[0], g, c[2]])
            for near in (1.5, .5, .28, .25):
                P.append((f'тень {cx},{cz} курс {k}', homer - fw * 3.6 + [0, 2.4, 0], homer + [0, 1.0, 0], 54., near))
    P += extra
    return P


def camf_poses(path):
    out = []; cur = '-'; prev = None
    for l in open(path, errors='replace'):
        if l.startswith('SCENE '): cur = l.split()[1]
        if l.startswith('CAMF '): prev = l
        if l.startswith('SHOT ') and prev:
            d = dict(re.findall(r'(\w+)=([^\s]+)', prev))
            if 'near' in d:
                out.append((f'CAMF {Path(path).parent.name}:{cur}', np.array([float(x) for x in d['eye'].split(',')]),
                            np.array([float(x) for x in d['look'].split(',')]), float(d['fov']), float(d['near'])))
    return out


def host_run(host, lines):
    return subprocess.run([host], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout.split('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', default=str(ROOT / 'build/level.shr')); ap.add_argument('--host', required=True); ap.add_argument('--host-old', required=True)
    ap.add_argument('--camf', nargs='*', default=[]); ap.add_argument('--radius', type=float, default=60.)
    a = ap.parse_args()
    L = level(a.level); shadow = shadow_tex(L)
    extra = [p for f in a.camf for p in camf_poses(f)]
    PS = poses(L, shadow, extra)
    print(f'{a.level}: треугольников {len(L["P"])}, текстуры «тень дерева» (полупрозрачные горизонтальные наклейки) {shadow}; поз {len(PS)} (из CAMF {len(extra)})')
    res = {}
    for label, host in (('прежнее', a.host_old), ('новое', a.host)):
        lost = collections.Counter(); lost_sh = collections.Counter(); bad_area = 0.; box_miss = 0; ncut = 0; worst = []; lost_15 = 0.
        for name, eye, at, fov, near in PS:
            r, u, f = basis(eye, at); tvy = math.tan(math.radians(fov) / 2); tvx = tvy * ASPECT
            rule = near < 1.5 * .999      # движок включает срез только в кадрах с ближней плоскостью ниже 1,5 м
            idx = np.nonzero(np.linalg.norm(L['C'] - eye, axis=1) < a.radius)[0]
            T = L['P'][idx] - eye; V = np.stack([T @ r, T @ u, T @ f], -1)
            x, y, z = V[..., 0], V[..., 1], V[..., 2]
            out = (z < near).all(1) | (x > tvx * z).all(1) | (-x > tvx * z).all(1) | (y > tvy * z).all(1) | (-y > tvy * z).all(1)
            vis = np.nonzero(~out)[0]
            cand = vis[((z[vis] < near * 1.01).any(1)) | (np.maximum(np.abs(x[vis] / np.maximum(z[vis], 1e-9) / tvx * 240),
                                                                     np.abs(y[vis] / np.maximum(z[vis], 1e-9) / tvy * 136)).max(1) >= 1800)]
            if not len(cand): continue
            if rule:
                outl = host_run(host, [f'T {tvx:.9g} {tvy:.9g} {near:.9g} ' + ' '.join(f'{v:.9g}' for v in V[k].ravel()) for k in cand])
            else:
                outl = ['0'] * len(cand)
            risky_pieces = set()
            for k, ln in zip(cand, outl):
                s = ln.split(); risk = int(s[0]) if s else 0
                gi = idx[k]; tex = int(L['TEX'][gi])
                ideal, _ = ge(V[k], near, tvx, tvy, band=False)
                if risk:
                    ncut += 1; risky_pieces.add(int(L['PI'][gi]))
                    n = int(s[1]); Pp = np.array([float(q) for q in s[2:2 + 3 * n]]).reshape(n, 3) if n else np.zeros((0, 3))
                    drawn = 0.; dl = 0.
                    for j in range(1, n - 1):
                        ar, drop = ge(Pp[[0, j, j + 1]], near, tvx, tvy)
                        if drop: dl += ar
                        else: drawn += ar
                    bad_area = max(bad_area, abs(drawn + dl - ideal)); lv = dl
                else:
                    ar, drop = ge(V[k], near, tvx, tvy); lv = ar if drop else 0.
                if lv > .5:
                    if rule: lost[name] += lv; lost_sh[name] += lv if tex in shadow else 0.
                    else: lost_15 += lv
            if rule and risky_pieces:   # бокс куска и клетки обязан быть «под риском»
                pcs = sorted(risky_pieces); cells = sorted({int(L['CELL'][np.nonzero(L['PI'] == p)[0][0]]) for p in pcs})
                lines = []
                for bb in [L['PBB'][p] for p in pcs] + [L['CBB'][c] for c in cells]:
                    cs = np.array([[bb[3] if q & 1 else bb[0], bb[4] if q & 2 else bb[1], bb[5] if q & 4 else bb[2]] for q in range(8)]) - eye
                    cc = np.stack([cs @ r, cs @ u, cs @ f], -1)
                    lines.append(f'B {tvx:.9g} {tvy:.9g} {near:.9g} ' + ' '.join(f'{v:.9g}' for v in cc.ravel()))
                box_miss += sum(1 for ln in host_run(host, lines) if ln.strip() == '0')
        tot = sum(lost.values()); tsh = sum(lost_sh.values())
        res[label] = dict(tot=tot, sh=tsh, bad=bad_area, miss=box_miss, cut=ncut, l15=lost_15)
        print(f'  {label}: кадры с ближней < 1,5 м — выброшено видимой площади {tot:.0f} px (тени {tsh:.0f} px, поз с потерями {len(lost)}); '
              f'нарезано треугольников {ncut}; расхождение веера с идеальным до {bad_area:.2f} px; промахов бокса {box_miss}')
        for nm, v in lost.most_common(5): print(f'    {nm}: {v:.0f} px (тени {lost_sh[nm]:.0f})')
        print(f'    при ближней 1,5 м (правило не включается) остаток: {lost_15:.0f} px')
    o, n = res['прежнее'], res['новое']
    ok = n['tot'] < .5 and n['miss'] == 0 and n['bad'] <= 1. and o['sh'] > 5000
    print(f'ИТОГ: {"зелёный" if ok else "КРАСНЫЙ"} — новое: потеряно {n["tot"]:.0f} px, промахов бокса {n["miss"]}, веер ±{n["bad"]:.2f} px; '
          f'прежнее: потеряно {o["tot"]:.0f} px, из них тени {o["sh"]:.0f} px ({"красный пойман" if o["sh"] > 5000 else "КРАСНЫЙ НЕ ПОЙМАН"})')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
