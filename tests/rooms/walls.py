#!/usr/bin/env python3
"""Камеры комнат не показывают стены «изнутри наружу» (правка Роба 27, 28.09, видео 4:16–4:22: «в доме Симпсонов камера
местами в стене, полкадра — стена»).

    python tests/rooms/walls.py [build/interiors-l1-gfx.bin] [--col build/interiors-l1.bin] [--plant double]

Гомер ставится в узлы сетки 1 м по полу каждой комнаты (земля COL1 комнаты, не внутри ящиков мебели); камера — та же, что
в EBOOT (viewer/roomcam.c через tests/rooms/view_host.c: триггеры, рельсы, FOV из данных); кадр 160×90 (16:9) —
программный растр с глубиной (tools/roomvis.c view), куски рисуются как в движке: с флагом 8 или без флага 128 —
с обеих сторон, остальные — только лицом (CCW).
Какая сторона треугольника «внутренняя», решает независимо от файла видимость из комнаты (глаза Гомера по полу,
tools/roomorient.py vote): видимая изнутри сторона — внутренняя; видимый изнутри с обеих сторон (мебель) — не оболочка.
  «изнутри наружу» — первым в пикселе виден треугольник оболочки своей НАРУЖНОЙ стороной: камера стоит за стеной
  (так расставлены камеры оригинала) и показывает её изнанку. Кадр плохой, если таких пикселей больше WALL_MAX.
  Провал — хоть один плохой кадр. «Пусто» — пиксели без треугольника (фон комнаты чёрный): сводка.
--plant double: заведомо плохой вход — все куски как двусторонние (рисование до правки 27) — обязан упасть."""
import argparse, struct, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import shr7read, roomorient   # noqa: E402

WALL_MAX = 0.10    # доля кадра
F_DOUBLE, F_SHELL = 8, 128
FW, FH = 160, 90


def col1(b, off):
    W, H, ntri, nbox = struct.unpack_from('<4I', b, off + 16)
    p = off + 48
    TR = np.frombuffer(b, '<f4', ntri * 12, p).reshape(-1, 4, 3).astype(np.float64); p += 48 * ntri
    BX = np.frombuffer(b, '<f4', nbox * 16, p).reshape(-1, 16).astype(np.float64)
    return TR, BX


def rooms_col(path):
    b = Path(path).read_bytes(); assert b[:4] == b'SHI1'
    nr, nd, ver = struct.unpack_from('<3I', b, 4); out = {}
    for i in range(nr):
        o = 16 + 128 * i; name = b[o:o + 32].split(b'\0')[0].decode(); coff, = struct.unpack_from('<I', b, o + 60)
        out[name] = col1(b, coff)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('gfx', nargs='?', default=str(ROOT / 'build/interiors-l1-gfx.bin'))
    ap.add_argument('--col', default=None, help='interiors-l1.bin (коллизия комнат; по умолчанию рядом)')
    ap.add_argument('--plant', choices=('double',))
    a = ap.parse_args()
    gfx = Path(a.gfx); colp = Path(a.col) if a.col else gfx.with_name('interiors-l1.bin')
    host = ROOT / 'build/rooms_cams/view_host'; host.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['cc', '-std=c99', '-O2', '-I', str(ROOT / 'viewer'), str(ROOT / 'tests/rooms/view_host.c'), str(ROOT / 'viewer/roomcam.c'),
                    '-lm', '-o', str(host)], check=True)
    rooms = shr7read.load_rooms(gfx); cols = rooms_col(colp)
    req = []
    for name, (TR, BX) in cols.items():
        if name in rooms: req += [f'{name} {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}' for p in roomorient.floor_points(TR, BX, 1.0)]
    res = subprocess.run([str(host), str(gfx)], input='\n'.join(req) + '\n', capture_output=True, text=True, check=True).stdout.splitlines()
    fails, notes, worst = [], [], []
    tmp = Path(tempfile.mkdtemp(prefix='walls_'))
    for name, d in rooms.items():
        if name not in cols: continue
        T = d['P']; TR, BX = cols[name]
        front, back = roomorient.vote(T, roomorient.eyes_of(TR, BX))
        flip, double, seen = roomorient.decide(front, back)
        side = np.where(double | ~seen, 0, np.where(front >= back, 1, -1)).astype(np.int8)   # +1: внутренняя — лицо
        drawn2 = ((d['FL'] & F_DOUBLE) != 0) | ((d['FL'] & F_SHELL) == 0)
        if a.plant == 'double': drawn2[:] = True
        roomorient.write_tris(tmp / 't.bin', T, drawn2.astype(np.uint8), side)
        views = [l.split() for l in res if l.startswith('VIEW ' + name + ' ') and l.split()[5] != '-1']
        V = np.array([[float(x) for x in v[8:14]] + [float(v[7]), FW / FH] for v in views], np.float32)
        with open(tmp / 'v.bin', 'wb') as f: f.write(struct.pack('<I', len(V))); f.write(V.tobytes())
        subprocess.run([str(roomorient.tool()), 'view', str(tmp / 't.bin'), str(tmp / 'v.bin'), str(tmp / 'o.bin'), '--w', str(FW), '--h', str(FH)], check=True)
        o = np.frombuffer((tmp / 'o.bin').read_bytes(), '<u4').reshape(-1, 3).astype(np.float64)
        outer = o[:, 2] / o[:, 0]; empty = o[:, 1] / o[:, 0]; bad = outer > WALL_MAX
        notes.append(f"{name}: кадров {len(V)}, с оболочкой изнутри наружу > {WALL_MAX:.0%}: {int(bad.sum())}; доля такой стены: средняя "
                     f"{outer.mean():.1%}, макс {outer.max():.1%}; пусто {empty.mean():.1%}; двусторонних кусков {int(drawn2.mean() * 100)}% треуг.")
        for i in np.nonzero(bad)[0]: worst.append((outer[i], name, views[i][6], views[i][2:5]))
        if bad.any(): fails.append(f"{name}: {int(bad.sum())} кадров из {len(V)} — камера за стеной показывает её изнанку")
    worst.sort(reverse=True)
    for w in worst[:4]: notes.append(f"   худший: {w[1]} камера {w[2]}, Гомер у ({', '.join(w[3])}) — изнанка стены {w[0]:.0%} кадра")
    print('FAIL: ' + fails[0] if fails else 'PASS: камеры комнат не показывают изнанку стен')
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
