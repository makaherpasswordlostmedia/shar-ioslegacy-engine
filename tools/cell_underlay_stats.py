"""Правка 509: статистика и проверка подложки по клеткам в готовом level.shr (читает Cell.pad: байт 1 глубина, байты 2–3 цвет RGB565).
Для каждой клетки: плоскость y = низ ящика − глубина·0,25 м; проверка по карте высот файла: плоскость не выше самой низкой опоры в квадрате 40 м
и в полосе соседей 4 м вокруг (иначе она торчала бы в щель). python tools/cell_underlay_stats.py LEVEL.shr [LEVEL2.shr …]"""
import struct, sys
import numpy as np
CHUNK, NB = 40.0, 4.0
def stats(path):
    b = open(path, 'rb').read()
    npc, = struct.unpack_from('<I', b, 8); ncell, ctab = struct.unpack_from('<II', b, 80)
    lo = struct.unpack_from('<3f', b, 12)[0:1]; hx, hz, hcell = struct.unpack_from('<3f', b, 12 + 11 * 4); W, H = struct.unpack_from('<II', b, 68)
    hm = np.frombuffer(b, '<i2', W * H * 4, 104).reshape(H, W, 4)
    cells = [struct.unpack_from('<6fIIIIII', b, ctab + 48 * i) for i in range(ncell)]
    city = [c for c in cells if c[8] == 0]
    cu = [c for c in city if c[11] >> 16]
    rgb = np.array([[(c[11] >> 27 & 31) * 255 // 31, (c[11] >> 21 & 63) * 255 // 63, (c[11] >> 16 & 31) * 255 // 31] for c in cu]) if cu else np.zeros((0, 3), int)
    dep = np.array([(c[11] >> 8 & 255) * 0.25 for c in cu]); viol = 0
    for c in cu:
        cx = int(np.floor((c[0] + c[3]) / 2 / CHUNK)); cz = int(np.floor((c[2] + c[5]) / 2 / CHUNK))
        y = c[1] - (c[11] >> 8 & 255) * 0.25
        g0 = int(np.floor((cx * CHUNK - NB - hx) / hcell)); g1 = int(np.floor(((cx + 1) * CHUNK + NB - hx) / hcell))
        z0 = int(np.floor((cz * CHUNK - NB - hz) / hcell)); z1 = int(np.floor(((cz + 1) * CHUNK + NB - hz) / hcell))
        g0r, g1r, z0r, z1r = max(0, g0), min(W - 1, g1), max(0, z0), min(H - 1, z1)
        raw_g0 = int(np.floor((cx * CHUNK - NB - hx) / hcell)); raw_z0 = int(np.floor((cz * CHUNK - NB - hz) / hcell))
        raw_g1 = int(np.floor(((cx + 1) * CHUNK + NB - hx) / hcell)); raw_z1 = int(np.floor(((cz + 1) * CHUNK + NB - hz) / hcell))
        outside = raw_g0 < 0 or raw_z0 < 0 or raw_g1 > W - 1 or raw_z1 > H - 1
        blk = hm[z0r:z1r + 1, g0r:g1r + 1].ravel() if g0r <= g1r and z0r <= z1r else np.zeros(0, np.int16); blk = blk[blk != -32768]
        if len(blk) and y > blk.min() / 100.0 - 0.25: viol += 1
        elif outside and y > c[1] - 2.5: viol += 1   # вне карты высот плоскость обязана быть ниже ящика минимум на запас
    return len(city), len(cu), rgb, dep, viol
for p in sys.argv[1:]:
    n, k, rgb, dep, viol = stats(p)
    if not k: print(f'{p}: подложки нет'); continue
    print(f'{p}: клеток города {n}, с подложкой {k}; цвет от {rgb.min(0).tolist()} до {rgb.max(0).tolist()}, средний {rgb.mean(0).round().astype(int).tolist()}, '
          f'яркость 10/50/90 % = {np.percentile(rgb.mean(1), [10, 50, 90]).round().astype(int).tolist()}; глубина под ящиком: медиана {np.median(dep):.2f} м, p90 {np.percentile(dep, 90):.2f} м, макс {dep.max():.1f} м; '
          f'плоскость выше опоры в квадрате или у соседей: {viol}')
