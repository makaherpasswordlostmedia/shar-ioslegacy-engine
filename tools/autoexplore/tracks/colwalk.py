"""Чтение COL1 уровня (viewer/col.h): примитивы в прямоугольнике. Хост, без игры."""
import struct, numpy as np
class Col:
    def __init__(s, path):
        d = open(path, 'rb').read(); off = struct.unpack_from('<I', d, 92)[0]; assert d[off:off + 4] == b'COL1'
        s.ox, s.oz, s.cell = struct.unpack_from('<3f', d, off + 4); s.W, s.H, nt, nb, nc, ns, nr, s.flags = struct.unpack_from('<8I', d, off + 16)
        p = off + 48
        s.tri = np.frombuffer(d, np.float32, nt * 12, p).reshape(nt, 12); p += nt * 48
        s.box = np.frombuffer(d, np.float32, nb * 16, p).reshape(nb, 16); p += nb * 64
        s.cyl = np.frombuffer(d, np.float32, nc * 12, p).reshape(nc, 12); p += nc * 48
        s.seg = np.frombuffer(d, np.float32, ns * 8, p).reshape(ns, 8); p += ns * 32
    def boxes_in(s, x0, x1, z0, z1):
        b = s.box; c = b[:, 0:3]; ax = b[:, 3:6]; ay = b[:, 6:9]; az = b[:, 9:12]; h = b[:, 12:15]
        ext = np.abs(ax) * h[:, 0:1] + np.abs(ay) * h[:, 1:2] + np.abs(az) * h[:, 2:3]
        sel = np.where((c[:, 0] + ext[:, 0] >= x0) & (c[:, 0] - ext[:, 0] <= x1) & (c[:, 2] + ext[:, 2] >= z0) & (c[:, 2] - ext[:, 2] <= z1))[0]
        return sel
if __name__ == '__main__':
    import sys
    C = Col(sys.argv[1]); x0, x1, z0, z1 = map(float, sys.argv[2:6]); np.set_printoptions(precision=2, suppress=True, linewidth=200)
    print('tri', len(C.tri), 'box', len(C.box), 'cyl', len(C.cyl), 'seg', len(C.seg))
    for i in C.boxes_in(x0, x1, z0, z1):
        b = C.box[i]; print('box', i, 'c', b[0:3], 'ax', b[3:6], 'ay', b[6:9], 'az', b[9:12], 'half', b[12:15], 'pad', b[15])
    for i, t in enumerate(C.tri):
        pass
