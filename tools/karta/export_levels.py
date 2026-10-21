#!/usr/bin/env python3
"""level.shr (SHR7) -> levels/lN.glb (город, текстуры) + levels/lN_col.glb (коллизия) + levels/lN.json (мета). Только локально."""
import sys, json, struct, io
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path.home() / 'Downloads/shar-psp/tools'))
import shr7read, blendmip_check as bm

PKG = Path.home() / 'Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721'
OUT = Path(__file__).parent / 'levels'
MAXTEX = 256

def glb(meshes, textures):
    """meshes: [(pos(N,3) f32, uv(N,2) f32|None, color(4) , tex idx|None, alphaMode)] -> bytes"""
    bin_ = bytearray(); views = []; acc = []; prims = []; imgs = []; texs = []; mats = []
    def add(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        views.append(dict(buffer=0, byteOffset=len(bin_), byteLength=len(data), **({'target': target} if target else {})))
        bin_.extend(data); return len(views) - 1
    tex_ix = {}
    for ti, png in textures.items():
        v = add(png); imgs.append(dict(bufferView=v, mimeType='image/png'))
        texs.append(dict(source=len(imgs) - 1, sampler=0)); tex_ix[ti] = len(texs) - 1
    mat_ix = {}
    nodes_prims = []
    for pos, uv, col, ti, am in meshes:
        key = (ti, am, tuple(col))
        if key not in mat_ix:
            m = dict(doubleSided=True, pbrMetallicRoughness=dict(baseColorFactor=list(col), metallicFactor=0, roughnessFactor=1))
            if ti is not None: m['pbrMetallicRoughness']['baseColorTexture'] = dict(index=tex_ix[ti])
            if am == 'MASK': m['alphaMode'] = 'MASK'; m['alphaCutoff'] = 0.25
            elif am == 'BLEND': m['alphaMode'] = 'BLEND'
            mats.append(m); mat_ix[key] = len(mats) - 1
        a = dict(POSITION=None); pos = np.ascontiguousarray(pos, '<f4')
        v = add(pos.tobytes(), 34962)
        acc.append(dict(bufferView=v, componentType=5126, count=len(pos), type='VEC3', min=pos.min(0).tolist(), max=pos.max(0).tolist()))
        attrs = dict(POSITION=len(acc) - 1)
        if uv is not None:
            v = add(np.ascontiguousarray(uv, '<f4').tobytes(), 34962)
            acc.append(dict(bufferView=v, componentType=5126, count=len(pos), type='VEC2')); attrs['TEXCOORD_0'] = len(acc) - 1
        prims.append(dict(attributes=attrs, material=mat_ix[key], mode=4))
    j = dict(asset=dict(version='2.0'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(mesh=0)], meshes=[dict(primitives=prims)],
             materials=mats, accessors=acc, bufferViews=views, buffers=[dict(byteLength=len(bin_))],
             samplers=[dict(magFilter=9728, minFilter=9987, wrapS=10497, wrapT=10497)])
    if imgs: j['images'] = imgs; j['textures'] = texs
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
    while len(bin_) % 4: bin_.append(0)
    return struct.pack('<4sII', b'glTF', 2, 28 + len(js) + len(bin_)) + struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(bin_), b'BIN\0') + bytes(bin_)

def png(rgba, w, h):
    im = Image.fromarray(np.ascontiguousarray(rgba, np.uint8), 'RGBA')
    if max(w, h) > MAXTEX: s = MAXTEX / max(w, h); im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BILINEAR)
    bio = io.BytesIO(); im.save(bio, 'PNG', optimize=False); return bio.getvalue()

def city(path):
    b = Path(path).read_bytes(); d = shr7read.load(path)
    T = bm.textures(b); P, UV, TEX, FL = d['P'], d['UV'], d['TEX'], d['FL']
    meshes = []; pngs = {}
    # FL: 1 alpha, 2 blend, 4 небо; небо пропускаем
    key = TEX * 4 + (FL & 3)
    for k in np.unique(key):
        m = (key == k) & ((FL & 4) == 0)
        if not m.any(): continue
        ti = int(k // 4); f = int(k % 4)
        if ti not in pngs and 0 <= ti < len(T):
            w, h, pal, lv = T[ti]; pngs[ti] = png(lv[0], w, h)
        am = 'BLEND' if f & 2 else ('MASK' if f & 1 else 'OPAQUE')
        meshes.append((P[m].reshape(-1, 3), UV[m].reshape(-1, 2), (1, 1, 1, 1), ti if ti in pngs else None, am))
    bb = (P.reshape(-1, 3).min(0).tolist(), P.reshape(-1, 3).max(0).tolist())
    return b, glb(meshes, pngs), len(P), bb

def colmesh(b):
    off, = struct.unpack_from('<I', b, 92)
    if not off: return None
    ox, oz, cell, W, H, ntri, nbox, ncyl, nseg, nref, flags = struct.unpack_from('<3f8I', b, off + 4)
    p = off + 48
    tri = np.frombuffer(b, '<f4', ntri * 12, p).reshape(ntri, 12); p += ntri * 48
    box = np.frombuffer(b, '<f4', nbox * 16, p).reshape(nbox, 16); p += nbox * 64
    cyl = np.frombuffer(b, '<f4', ncyl * 12, p).reshape(ncyl, 12); p += ncyl * 48
    seg = np.frombuffer(b, '<f4', nseg * 8, p).reshape(nseg, 8)
    V = []
    # ящики: c, ax, ay, az (оси единичные), h = полуразмеры
    C = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for r in box:
        c, ax, ay, az, h = r[0:3], r[3:6], r[6:9], r[9:12], r[12:15]
        pts = c + (C[:, :1] * h[0]) * ax + (C[:, 1:2] * h[1]) * ay + (C[:, 2:] * h[2]) * az
        for q in F: V += [pts[q[0]], pts[q[1]], pts[q[2]], pts[q[0]], pts[q[2]], pts[q[3]]]
    # цилиндры/капсулы: приблизим ящиком вдоль оси (8-гранная призма)
    for r in cyl:
        c, ax, rad, hl = r[0:3].astype(float), r[3:6].astype(float), float(r[6]), float(r[7])
        ax /= (np.linalg.norm(ax) or 1); t = np.array([1, 0, 0]) if abs(ax[0]) < .9 else np.array([0, 1, 0])
        u = np.cross(ax, t); u /= np.linalg.norm(u); v = np.cross(ax, u)
        ring = [u * np.cos(a) * rad + v * np.sin(a) * rad for a in np.linspace(0, 2 * np.pi, 9)[:-1]]
        e = hl + (rad if r[8] == 0 else 0)
        for i in range(8):
            a, bb_ = ring[i], ring[(i + 1) % 8]
            A0, B0, A1, B1 = c - ax * e + a, c - ax * e + bb_, c + ax * e + a, c + ax * e + bb_
            V += [A0, B0, B1, A0, B1, A1]
    # заборы: полоса 4 м над землёй (y среднее по ближайшим треугольникам земли; иначе 0)
    gy = tri[:, [1, 4, 7]].mean(1) if ntri else np.zeros(0); gx = tri[:, [0, 3, 6]].mean(1) if ntri else gy; gz = tri[:, [2, 5, 8]].mean(1) if ntri else gy
    for s in seg:
        mx, mz = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2; y = 0.0
        if ntri:
            d = (gx - mx) ** 2 + (gz - mz) ** 2; y = float(gy[np.argmin(d)])
        a = np.array([s[0], y, s[1]]); bb_ = np.array([s[2], y, s[3]]); up = np.array([0, 3.5, 0])
        V += [a, bb_, bb_ + up, a, bb_ + up, a + up]
    # стены из ColTri (n.y < 0.5)
    wall = tri[tri[:, 10] < 0.5] if ntri else tri
    for r in wall: V += [r[0:3], r[3:6], r[6:9]]
    pos = np.array(V, np.float32).reshape(-1, 3) if V else None
    st = dict(box=int(nbox), cyl=int(ncyl), seg=int(nseg), wallTri=int(len(wall)), groundTri=int(ntri))
    return (glb([(pos, None, (1.0, 0.25, 0.2, 0.45), None, 'BLEND')], {}) if pos is not None else None), st

if __name__ == '__main__':
    for n in sys.argv[1:]:
        path = PKG / ('level.shr' if n == '1' else f'l{n}/level.shr')
        print('L' + n, path, flush=True)
        b, g, ntri, bb = city(path)
        (OUT / f'l{n}.glb').write_bytes(g)
        c, st = colmesh(b)
        if c: (OUT / f'l{n}_col.glb').write_bytes(c)
        spawn = struct.unpack_from('<4f', b, 36)
        ox, oz = struct.unpack_from('<2f', b, b.find(b'COL1') + 4) if b.find(b'COL1') > 0 else (0, 0)
        (OUT / f'l{n}.json').write_text(json.dumps(dict(level=int(n), tris=int(ntri), bbox=bb, spawn=dict(x=spawn[0], y=spawn[1], z=spawn[2], heading=spawn[3]), col=st, hasCol=bool(c))))
        print('  tris', ntri, 'glb MB', len(g) / 1e6, st, flush=True)
