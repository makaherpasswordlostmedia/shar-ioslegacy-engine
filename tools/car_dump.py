#!/usr/bin/env python3
"""Проба машины игрока: скелет, куски→суставы, шейдеры/текстуры урона, локаторы, блики, физ-суставы.

Только чтение ресурсов с диска Роба (hit-and-run-web/source/game). Ничего не пишет.
Форматы чанков — donut/dev/Chunks.md (GPL) и Pure3D/src/Pure3D/Chunks (Locator, BillboardQuad).

  .venv/bin/python tools/car_dump.py                 # famil_v
  .venv/bin/python tools/car_dump.py famil_v --husk  # + huska.p3d и блики common.p3d
  .venv/bin/python tools/car_dump.py cpolice         # любая машина из art/cars

Координаты — как в файле Pure3D (левая система, модель смотрит в -Z; движок SHR зеркалит z).
"""
import sys, struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string          # noqa: E402  (MIT)
from convert import geometry                # noqa: E402  (MIT) — разбор PrimitiveGroup (VIF PS2)

GAME = ROOT / 'hit-and-run-web/source/game'
CARS = GAME / 'art/cars'


def nm(c, off=0):
    try: return string(c.data, off)[0]
    except Exception: return '?'


def f32(b, n, p): return struct.unpack_from('<%df' % n, b, p)


# ---------- скелет ----------
def skeleton(sk):
    """[(name, parent, local4x4, world4x4)] — матрицы строкой (Pure3D: вектор-строка, перенос в [3,:3])."""
    out = []
    for j in (c for c in sk.children if c.id == 0x4501):
        name, p = string(j.data)
        parent, dof, free, prim, sec, twist = struct.unpack_from('<I5i', j.data, p)
        M = np.array(f32(j.data, 16, p + 24), dtype=np.float64).reshape(4, 4)
        W = M @ out[parent][3] if out and parent < len(out) and parent != len(out) else M
        out.append((name, parent, M, W, dof))
    return out


def mesh_info(m):
    """Сводка меша: шейдеры, треугольники, bbox (в координатах меша, до зеркала z)."""
    prims, lo, hi, has_shadow = [], np.full(3, 1e9), np.full(3, -1e9), False
    for pg in m.children:
        if pg.id == 0x10017: has_shadow = True
        if pg.id != 0x10002: continue
        shader, parts = geometry(pg)
        tris = 0
        for part in parts:
            P = part['position'].copy(); P[:, 2] *= -1        # geometry() уже зеркалит z — вернём как в файле
            lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0)); tris += len(part['indices']) // 3
        prims.append((shader, tris))
    return prims, lo, hi, has_shadow


def shaders(root):
    out = {}
    for c in walk(root):                      # common.p3d держит шейдеры внутри групп бликов
        if c.id != 0x11000: continue
        name, p = string(c.data); _ver, = struct.unpack_from('<I', c.data, p); kind, p = string(c.data, p + 4)
        props = {}
        for pr in c.children:
            key = pr.data[:4].rstrip(b'\0').decode('ascii', 'replace')
            if pr.id == 0x11002: props.setdefault(key, []).append(string(pr.data, 4)[0])
            elif pr.id == 0x11003: props[key] = struct.unpack_from('<I', pr.data, 4)[0]
            elif pr.id == 0x11004: props[key] = round(struct.unpack_from('<f', pr.data, 4)[0], 3)
            elif pr.id == 0x11005: props[key] = '#%08x' % struct.unpack_from('<I', pr.data, 4)[0]
        out[name] = (kind, props)
    return out


def billboards(root):
    out = []
    for g in (c for c in walk(root) if c.id == 0x17002):
        ver, = struct.unpack_from('<I', g.data); gname, p = string(g.data, 4); sh, p = string(g.data, p)
        zt, zw, fog, nq = struct.unpack_from('<4I', g.data, p)
        for q in (c for c in g.children if c.id == 0x17001):
            qn, p = string(q.data, 4); mode = q.data[p:p + 4].rstrip(b'\0').decode('ascii', 'replace'); p += 4
            t = f32(q.data, 3, p); col, = struct.unpack_from('<I', q.data, p + 12)
            w, h, dist = f32(q.data, 3, p + 16 + 32)
            out.append((gname, sh, qn, mode, t, col, w, h, dist, zt, zw))
    return out


def dump_car(path, show_mesh=True):
    root = read(path)
    print(f'== {path.relative_to(GAME)}')
    sh = shaders(root)
    tex = [nm(c) for c in root.children if c.id == 0x19000]
    print(f'текстуры ({len(tex)}):', ', '.join(tex))
    meshes = {nm(c): c for c in root.children if c.id == 0x10000}

    # композит → скелет
    comp = next((c for c in root.children if c.id == 0x4512), None)
    sks = {nm(c): c for c in root.children if c.id == 0x4500}
    if comp is not None:
        cname, p = string(comp.data); skname, _ = string(comp.data, p)
        J = skeleton(sks[skname])
        props = []
        for c in walk(comp):
            if c.id == 0x4516:
                dn, p = string(c.data); trans, joint = struct.unpack_from('<II', c.data, p)
                so = next((struct.unpack_from('<f', s.data)[0] for s in c.children if s.id == 0x4519), None)
                props.append((dn, trans, joint, so))
        eff = [c for c in walk(comp) if c.id in (0x4517, 0x4518)]
        print(f'\n-- скелет {skname}: {len(J)} суставов (мировая позиция покоя, м; dof)')
        att = {}
        for dn, tr, j, so in props: att.setdefault(j, []).append(dn + ('*' if tr else ''))
        for i, (n, par, M, W, dof) in enumerate(J):
            depth, k = 0, i
            while k != 0 and depth < 16: k = J[k][1]; depth += 1
            print(f'  {i:2d} {"  " * depth}{n:<14} parent={par:<3} pos=({W[3,0]:+.3f},{W[3,1]:+.3f},{W[3,2]:+.3f})'
                  f' local=({M[3,0]:+.3f},{M[3,1]:+.3f},{M[3,2]:+.3f}) dof={dof}'
                  + (f'  ← {", ".join(att[i])}' if i in att else ''))
        print(f'\n-- композит {cname}: {len(props)} кусков (* = прозрачный), эффекты: {[hex(e.id) for e in eff]}')
        for dn, tr, j, so in props:
            print(f'  {dn:<16} → сустав {j:2d} {J[j][0]:<12} trans={tr} sort={so}')
        for n2, sk in sks.items():
            if n2 == skname: continue
            J2 = skeleton(sk)
            print(f'\n-- доп. скелет {n2} ({len(J2)}): ' + ', '.join(f'{j[0]}' for j in J2))

    if show_mesh:
        print('\n-- меши (bbox в координатах меша; куски на суставах рисуются матрицей сустава)')
        for n, m in meshes.items():
            prims, lo, hi, shd = mesh_info(m)
            ptxt = ', '.join(f'{s}:{t}' for s, t in prims)
            print(f'  {n:<16} tris={sum(t for _, t in prims):5d} bbox=({lo[0]:+.2f},{lo[1]:+.2f},{lo[2]:+.2f})..'
                  f'({hi[0]:+.2f},{hi[1]:+.2f},{hi[2]:+.2f}){"  [DrawShadow]" if shd else ""}\n      {ptxt}')

    print('\n-- шейдеры (тип, TEX, флаги)')
    for n, (kind, pr) in sh.items():
        print(f'  {n:<22} {kind:<10} {pr}')
    dam = [t for t in tex if 'Dam' in t]
    print('\n-- урон: целая → битая текстура')
    for d in dam:
        norm = d.replace('Dam', 'Norm')
        users = [n for n, (_, pr) in sh.items() if norm.lower() in [x.lower() for x in pr.get('TEX', [])]]
        print(f'  {norm:<22} → {d:<22} шейдеры: {users}')

    loc = [(nm(c), c) for c in root.children if c.id == 0x14000]
    if loc:
        print('\n-- локаторы (0x14000: name, version, pos)')
        for n, c in loc:
            _, p = string(c.data); ver, = struct.unpack_from('<I', c.data, p); pos = f32(c.data, 3, p + 4)
            print(f'  {n:<10} ({pos[0]:+.3f},{pos[1]:+.3f},{pos[2]:+.3f})')

    bb = billboards(root)
    if bb:
        print('\n-- блики BillboardQuadGroup (группа, шейдер, квад, режим, позиция, цвет, w×h, дистанция, zTest/zWrite)')
        for g, s, q, mode, t, col, w, h, d, zt, zw in bb:
            print(f'  {g:<14} {s:<16} {q:<14} {mode:<4} ({t[0]:+.3f},{t[1]:+.3f},{t[2]:+.3f}) #{col:08x} {w:.2f}×{h:.2f} d={d:.2f} z={zt}/{zw}')

    for po in (c for c in root.children if c.id == 0x7011000):
        # Pure3D PhysicsObject.cs: name, version, material, numJoints, volume, restingSensitivity
        pn, p = string(po.data); ver, = struct.unpack_from('<I', po.data, p); mat, p = string(po.data, p + 4)
        nj, vol, sens = struct.unpack_from('<Iff', po.data, p)
        print(f'\n-- PhysicsObject {pn} material={mat} joints={nj} volume={vol:.3f} restingSensitivity={sens:.3f}')
        for j in (c for c in po.children if c.id == 0x7011020):
            # PhysicsJoint.cs: index, volume, stiffness, maxAngle, minAngle, DOF(u32)
            idx, vol, stiff, amax, amin, dof = struct.unpack_from('<I4fI', j.data)
            vec = [f32(v.data, 3, 0) for v in j.children if v.id == 0x7011002]
            jn = J[idx][0] if comp is not None and idx < len(J) else '?'
            print(f'  joint {idx:2d} {jn:<10} volume={vol:.3f} stiffness={stiff:.3f} max={amax:+.3f} min={amin:+.3f} rad'
                  f' ({amax * 57.2958:+.0f}..{amin * 57.2958:+.0f} град) dof={dof}'
                  + (f' vec={[round(x, 3) for x in vec[0]]}' if vec else ''))

    for c in root.children:
        if c.id == 0x3000100:
            print(f'\n-- FollowCameraData: {[round(x, 3) for x in f32(c.data, 7, 0)]}')
    return root


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    car = args[0] if args else 'famil_v'
    dump_car(CARS / f'{car}.p3d')
    if '--husk' in sys.argv:
        print('\n' + '=' * 70); dump_car(CARS / 'huska.p3d')
        print('\n' + '=' * 70); dump_car(CARS / 'common.p3d')
