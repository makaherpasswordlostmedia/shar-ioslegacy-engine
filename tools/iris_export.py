#!/usr/bin/env python3
"""Ирис оригинала (Scrooby 3dIris.pag -> pure3d\\iris.p3d) -> build/iris.shr для viewer/transit.c.

Что лежит на диске (art/frontend/scrooby/resource/pure3d/iris.p3d, разбор этого файла):
  * pCylinderShape1 — плоский диск радиуса 8.74 в плоскости XY (20 секторов, 40 треугольников, 120 вершин списком),
    шейдер iris_black (simple, DIFF 0x000000);
  * OffsetList (0x1000E) — морф-цель: центральные вершины секторов уезжают к радиусу 7.636 (отверстие диафрагмы);
  * Expression khgfkjhf (0x21000) -> ExpressionGroup p3dGroup1: вес морфа = значение канала;
  * анимация EXP_p3dGroup1 (0x121000): 26 кадров, 30 кадр/с, канал STE (Float1): кадры 0/10/15/25 -> 1/0/0/1
    (1 — открыто, 0 — закрыто: закрывается 10 кадров, закрыто 5, открывается 10);
  * камера IrisCameraShape: fov 0.95 рад (горизонтальный: иначе закрытый диск не закрыл бы углы 4:3), z = -11.525.
Экран IrisWipe.scr = 3dIris.pag + LoadingText.pag; LetterBox.scr = LetterBox.pag + LetterBoxButtons.pag + 3dIris.pag.

Формат IRS1 (little-endian):
  'IRS1' u32 nvert, f32 fps, f32 nframes, u32 nkeys, f32 fov, f32 camDist, u32 abgr,
  nkeys × (f32 frame, f32 value), nvert × (f32 x, f32 y), nvert × (f32 dx, f32 dy)
Читает только диск и hit-and-run-web/tools/p3d.py (MIT).

    python tools/iris_export.py [--out build/iris.shr] [--check]
"""
import argparse
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string  # noqa: E402

SRC = ROOT / 'hit-and-run-web/source/game/art/frontend/scrooby/resource/pure3d/iris.p3d'


def fourcc(b, p):
    return b[p:p + 4].rstrip(b'\0').decode('latin1')


def parse(path=SRC):
    root = read(path)
    pos = off = None; keys = None; fps = nframes = None; fov = dist = None; diff = 0xff000000
    for c in walk(root):
        d = c.data
        if c.id == 0x10005 and pos is None:                       # PositionList первой (единственной) группы
            n, = struct.unpack_from('<I', d, 0)
            pos = [struct.unpack_from('<3f', d, 4 + 12 * i) for i in range(n)]
        elif c.id == 0x1000E:                                     # OffsetList: n, primgroup, n × (index, vec3)
            n, _pg = struct.unpack_from('<2I', d, 0)
            off = {}
            for i in range(n):
                k, x, y, z = struct.unpack_from('<I3f', d, 8 + 16 * i)
                off[k] = (x, y, z)
        elif c.id == 0x121000:                                    # Animation: version, name, type, frames, rate, cyclic
            _v, = struct.unpack_from('<I', d, 0); name, p = string(d, 4)
            typ = fourcc(d, p); nf, rate = struct.unpack_from('<2f', d, p + 4)
            if typ == 'EXP':
                for s in walk(c):
                    if s.id == 0x121100:                          # Float1Channel: version, param, n, frames u16[n], values f32[n]
                        param = fourcc(s.data, 4); n, = struct.unpack_from('<I', s.data, 8)
                        fr = struct.unpack_from('<%dH' % n, s.data, 12)
                        q = 12 + 2 * n
                        va = struct.unpack_from('<%df' % n, s.data, q)
                        if param == 'STE':
                            keys = list(zip([float(x) for x in fr], va)); fps = rate; nframes = nf
        elif c.id == 0x2200:                                      # Camera: name, version, fov, aspect, near, far, pos, look, up
            name, p = string(d, 0)
            _v, fov_, _asp, _n, _f, px, py, pz = struct.unpack_from('<I7f', d, p)
            fov = fov_; dist = abs(pz)
        elif c.id == 0x11005 and fourcc(d, 0) == 'DIFF':          # шейдер iris_black: цвет ARGB
            diff, = struct.unpack_from('<I', d, 4)
    if pos is None or off is None or keys is None or fov is None:
        raise SystemExit('iris.p3d: нет сетки, морфа, анимации или камеры')
    return pos, off, keys, fps, nframes, fov, dist, diff


def argb_to_abgr(c):
    a, r, g, b = (c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255, c & 255
    return (a << 24) | (b << 16) | (g << 8) | r


def pack(out):
    pos, off, keys, fps, nframes, fov, dist, diff = parse()
    b = bytearray(b'IRS1')
    b += struct.pack('<If f I ff I'.replace(' ', ''), len(pos), fps, nframes, len(keys), fov, dist, argb_to_abgr(diff) | 0xff000000)
    for fr, v in keys:
        b += struct.pack('<2f', fr, v)
    for x, y, _z in pos:
        b += struct.pack('<2f', x, y)
    for i in range(len(pos)):
        dx, dy, _dz = off.get(i, (0.0, 0.0, 0.0))
        b += struct.pack('<2f', dx, dy)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(b))
    return pos, off, keys, fps, nframes, fov, dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'build/iris.shr'))
    ap.add_argument('--check', action='store_true', help='распечатать разбор (радиус отверстия, ключи, масштаб)')
    a = ap.parse_args()
    pos, off, keys, fps, nframes, fov, dist = pack(Path(a.out))
    if a.check:
        rim = max(math.hypot(x, y) for x, y, _ in pos)
        hole = [math.hypot(pos[k][0] + d[0], pos[k][1] + d[1]) for k, d in off.items()]
        k_src = 320.0 / (dist * math.tan(fov / 2))
        print(f'verts {len(pos)} tris {len(pos) // 3} rim {rim:.3f} hole r {min(hole):.3f}..{max(hole):.3f} ({len(off)} морф-вершин)')
        print(f'keys {keys} fps {fps} frames {nframes}; camera fov {fov:.4f} dist {dist:.3f} -> {k_src:.2f} px/ед на 640')
        print(f'4:3: открыто {min(hole) * math.cos(math.pi / 20) * k_src:.0f} px, диск {rim * k_src:.0f} px, полудиагональ 400 px')
    print(f'iris: {a.out}')


if __name__ == '__main__':
    main()
