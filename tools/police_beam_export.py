#!/usr/bin/env python3
"""Большие лучи мигалок cpolice (правка Роба 495, Г16): четыре NOAX-квада siren6/siren8 (10,42 x 2,69 м) и sirenShape7/sirenShape9
(16,3 x 2,69 м) с диска. NOAX — без оси: квад лежит в плоскости XY своего сустава и поворачивается вместе с ним; суставы siren6..9 крутит
клип PTRN_cPolice (ROT, 21 кадр, 24 к/с) вокруг вертикали — лучи качаются над крышей. Данные: углы квадов в модели машины на каждом
кадре клипа (кватернион между ключами — по кратчайшей дуге), цвет и UV квада с диска. Тот же scratch2.bmp, что у мигалок (pfTexture).
  python tools/police_beam_export.py [--out viewer/police_beam_data.h]"""
import argparse, hashlib, math, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'hit-and-run-web/tools')]
from p3d import read, walk, string
from car_dump import skeleton, billboards, shaders
from frontend3d_export import anims

BEAMS = ('siren6Shape', 'siren8Shape', 'sirenShape7', 'sirenShape9')


def qmat(q, order):
    """кватернион -> матрица для вектора-строки (Pure3D), порядок компонент wxyz или xyzw"""
    w, x, y, z = (q[0], q[1], q[2], q[3]) if order == 'wxyz' else (q[3], q[0], q[1], q[2])
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0; w, x, y, z = w / n, x / n, y / n, z / n
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return R.T


def slerp(a, b, u):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = float(a @ b)
    if d < 0: b, d = -b, -d
    if d > 0.9995:
        r = a + (b - a) * u; return r / np.linalg.norm(r)
    th = math.acos(min(1.0, d)); s = math.sin(th)
    return (math.sin((1 - u) * th) * a + math.sin(u * th) * b) / s


def track(keys, vals, f, frames):
    """значение дорожки ROT на кадре f (цикл по frames)"""
    keys = list(keys); vals = [np.asarray(v, float) for v in vals]
    if len(keys) == 1: return vals[0]
    f = f % frames
    for i in range(len(keys)):
        k0, k1 = keys[i], keys[(i + 1) % len(keys)] + (frames if i + 1 == len(keys) else 0)
        ff = f if f >= k0 else f + frames
        if k0 <= ff <= k1 and k1 > k0: return slerp(vals[i], vals[(i + 1) % len(keys)], (ff - k0) / (k1 - k0))
    return vals[0]


def source():
    path = ROOT / 'hit-and-run-web/source/game/art/cars/cpolice.p3d'; r = read(path)
    comp = next(c for c in r.children if c.id == 0x4512); _, p = string(comp.data); sk, _ = string(comp.data, p)
    joints = skeleton(next(c for c in r.children if c.id == 0x4500 and string(c.data)[0] == sk))
    bind = {}
    for c in walk(comp):
        if c.id == 0x4516:
            n, p = string(c.data); _, j = struct.unpack_from('<II', c.data, p); bind[n] = j
    ptrn = anims(r)['PTRN_cPolice']; frames = ptrn[1]; fps = ptrn[2]; ch = ptrn[3]
    sh = shaders(r); rows = []
    for g, shn, n, mode, pos, col, w, h, dist, zt, zw in billboards(r):
        if n not in BEAMS: continue
        assert mode == 'NOAX' and sh[shn][1]['TEX'] == ['scratch2.bmp'] and sh[shn][1]['BLMD'] == 2 and np.allclose(pos, 0) and dist == 0
        j = bind[g]; name, parent, M, W, dof = joints[j]
        keys, quats = ch[name]['ROT']; tk, tv = ch[name]['TRAN']
        # порядок компонент: по первому кадру — должен дать ту же вращательную часть, что покоящаяся локальная матрица сустава
        order = next(o for o in ('wxyz', 'xyzw') if np.allclose(qmat(track(keys, quats, 0, frames), o), M[:3, :3], atol=1e-3))
        quad = next(c for c in walk(r) if c.id == 0x17001 and string(c.data, 4)[0] == n)
        _, p = string(quad.data, 4); uv = struct.unpack_from('<8f', quad.data, p + 4 + 12 + 4)
        PW = joints[parent][3]; frames_xyz = []
        for f in range(frames):
            L = np.eye(4); L[:3, :3] = qmat(track(keys, quats, f, frames), order); L[3, :3] = tv[0]
            Wf = L @ PW
            cor = []
            for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1)):
                v = (np.r_[sx * w * .5, sy * h * .5, 0., 1.] @ Wf)[:3]; v[2] *= -1; cor.append(v.tolist())   # z зеркалится, как у мигалок
            frames_xyz.append(cor)
        a, rr, gg, bb = (col >> 24) & 255, (col >> 16) & 255, (col >> 8) & 255, col & 255   # ARGB диска -> ABGR для GU
        rows.append(dict(name=n, color=(a << 24) | (bb << 16) | (gg << 8) | rr, uv=uv, w=w, h=h, corners=frames_xyz))
    assert len(rows) == 4 and frames == 21
    rows.sort(key=lambda x: x['name'])
    return path, rows, frames, fps


def ff(x):
    s = format(float(x), '.9g'); return s + ('' if '.' in s or 'e' in s else '.0') + 'f'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT / 'viewer/police_beam_data.h'); a = ap.parse_args()
    path, rows, frames, fps = source()
    L = ['// Родной cpolice.p3d SHA256 ' + hashlib.sha256(path.read_bytes()).hexdigest() + ' (tools/police_beam_export.py, правка 495)',
         '#ifndef POLICE_BEAM_DATA_H', '#define POLICE_BEAM_DATA_H', f'#define PB_COUNT {len(rows)}', f'#define PB_FRAMES {frames}', f'#define PB_FPS {ff(fps)}',
         'typedef struct { char name[16]; unsigned color; float uv[8]; float c[PB_FRAMES][4][3]; } PbDef;', 'static const PbDef pbDefs[PB_COUNT] = {']
    for r in rows:
        L.append('{"' + r['name'] + '",' + hex(r['color']) + 'u,{' + ','.join(map(ff, r['uv'])) + '},{')
        for fr in r['corners']: L.append('{' + ','.join('{' + ','.join(map(ff, v)) + '}' for v in fr) + '},')
        L.append('}},')
    L += ['};', '#endif', '']
    a.out.write_text('\n'.join(L)); print('beams', len(rows), 'frames', frames, '->', a.out)


if __name__ == '__main__': main()
