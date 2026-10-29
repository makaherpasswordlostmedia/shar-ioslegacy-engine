"""Дороги уровня для бота cartest: отрезки 0x3000002 из l{N}_terra.p3d (как в hit-and-run-web/tools/convert.py:
середины торцов четырёхугольника дороги, z отзеркален). Пишет float32 N x 7: ax ay az bx by bz halfWidth.
python tools/cartest/roads.py [--level 1] --out roads.bin
Рядом пишет roads.meta.tsv (01.10, группа corners-roads): по строке на отрезок в том же порядке — дорога 0x3000003, которой он
принадлежит, и её поля из данных: maxCars, speed, intelligence, shortcut (после имени, типа u32 и двух имён перекрёстков:
u32 maxCars, затем байты speed, intelligence, shortcut). shortcut=1 и maxCars=0 — срезка ИИ (гонки/погоня через трамплины и
дворы), машин трафика на ней нет: «дорога трафика» для проверок — только maxCars > 0 и shortcut = 0."""
import sys, struct, argparse
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string

def floats(b, n, p=0): return np.frombuffer(b, '<f4', n, p).astype(np.float64)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    terra = read(ROOT / f'hit-and-run-web/source/game/art/l{a.level}_terra.p3d')
    defs = {string(c.data)[0]: c for c in terra.children if c.id == 0x3000009}
    out = []
    for c in walk(terra):
        if c.id != 0x3000002: continue
        name, p = string(c.data); dname, p = string(c.data, p)
        T = floats(c.data, 16, p).reshape(4, 4); S = floats(c.data, 16, p + 64).reshape(4, 4)
        d = defs[dname]; _, q = string(d.data)
        pts = np.concatenate([np.zeros((1, 3)), floats(d.data, 9, q + 12).reshape(3, 3)])
        pts = np.c_[pts, np.ones(4)] @ S @ T
        pts[:, 2] *= -1
        A = (pts[0, :3] + pts[3, :3]) / 2; B = (pts[1, :3] + pts[2, :3]) / 2
        hw = (np.linalg.norm(pts[0, :3] - pts[3, :3]) + np.linalg.norm(pts[1, :3] - pts[2, :3])) / 4
        out.append([*A, *B, hw])
    R = np.array(out, np.float32)
    Path(a.out).write_bytes(R.tobytes())
    road = {}   # отрезок -> (дорога, maxCars, speed, intelligence, shortcut)
    for c in terra.children:
        if c.id != 0x3000003: continue
        rn, p = string(c.data); p += 4; _, p = string(c.data, p); _, p = string(c.data, p)
        mc, = struct.unpack_from('<I', c.data, p); sp, it, sc = c.data[p + 4], c.data[p + 5], c.data[p + 6]
        for k in c.children: road[string(k.data)[0]] = (rn, mc, sp, it, sc)
    segs = [string(c.data)[0] for c in walk(terra) if c.id == 0x3000002]
    meta = Path(a.out).with_suffix('.meta.tsv')
    meta.write_text('# отрезок\tдорога\tmaxCars\tspeed\tintelligence\tshortcut (tools/cartest/roads.py)\n' +
                    ''.join(f'{n}\t' + '\t'.join(map(str, road.get(n, ('-', 0, 0, 0, 0)))) + '\n' for n in segs))
    tr = sum(1 for n in segs if road.get(n, ('', 0, 0, 0, 1))[1] > 0 and not road.get(n, ('', 0, 0, 0, 1))[4])
    print(f'roads: {meta.name}: отрезков дорог трафика (maxCars > 0, не срезка) {tr} из {len(segs)}')
    L = np.linalg.norm(R[:, 3:6] - R[:, 0:3], axis=1)
    print(f'roads: {len(R)} segments, length total {L.sum():.0f} m, per seg median {np.median(L):.1f} max {L.max():.1f}, '
          f'half width median {np.median(R[:, 6]):.1f}; x {R[:, [0, 3]].min():.0f}..{R[:, [0, 3]].max():.0f} '
          f'z {R[:, [2, 5]].min():.0f}..{R[:, [2, 5]].max():.0f}')

if __name__ == '__main__': main()
