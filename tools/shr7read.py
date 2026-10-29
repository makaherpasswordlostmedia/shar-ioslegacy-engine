"""Чтение треугольников из SHR7 (город, машина, небо — tools/psp_export.py) и SHG1 (комнаты — tools/interior_export.py)
вместе с UV (так, как их читает GE: u16 / 256, tools/uvq.py), флагами и текстурой куска — для проверок рисования
(tools/decals.py, tools/seams.py). Только чтение.
  load(path, far=False, owner=0) -> dict(P (N,3,3) мир, UV (N,3,2), TEX, FL, PI (номер куска), CELL,
                                          OFF (байт первой вершины треугольника в файле), VS (размер вершины))
  load_rooms(path)               -> {имя комнаты: тот же dict (OFF — от начала файла)}"""
import struct
from pathlib import Path
import numpy as np

F_NOIDX, F_V12 = 16, 32


def _tris(b, base, fl, cnt, sc, o):
    vs = 12 if fl & F_V12 else 16
    raw = np.frombuffer(b, np.uint8, cnt * vs, base).reshape(cnt, vs)
    uv = raw[:, 0:4].copy().view('<u2').reshape(cnt, 2).astype(np.float64) / 256   # как читает GE: без знака (tools/uvq.py)
    xyz = (raw[:, 6:12] if vs == 12 else raw[:, 8:14]).copy().view('<i2').reshape(cnt, 3)
    w = xyz.astype(np.float64) * (sc / 32768.0) + np.asarray(o, np.float64)
    return w.reshape(-1, 3, 3), uv.reshape(-1, 3, 2), vs


def _pack(L):
    keys = ('P', 'UV', 'TEX', 'FL', 'PI', 'CELL', 'OFF', 'VS')
    shapes = {'P': (0, 3, 3), 'UV': (0, 3, 2)}
    out = {}
    for k in keys:
        a = [x[k] for x in L]
        out[k] = np.concatenate(a) if a else np.zeros(shapes.get(k, (0,)))
        if k not in ('P', 'UV'): out[k] = out[k].astype(np.int64)
    return out


def load(path, far=False, owner=0):
    b = Path(path).read_bytes()
    assert b[:4] == b'SHR7', 'не SHR7'
    ntex, npc = struct.unpack_from('<II', b, 4)
    ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    L = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        tex, fl, nv, ni, own = r[6:11]; ox, oy, oz, sc = r[11:15]; off, nf, ci = r[15:18]
        if own != owner or ni == 0 or not fl & F_NOIDX: continue   # старый индексный формат не читаем
        first, cnt = (ni, nf) if far else (0, ni)
        if cnt == 0: continue
        vs = 12 if fl & F_V12 else 16
        base = cells[ci][9] + off + first * vs
        p, uv, vs = _tris(b, base, fl, cnt, sc, (ox, oy, oz)); m = len(p)
        L.append(dict(P=p, UV=uv, TEX=np.full(m, tex), FL=np.full(m, fl), PI=np.full(m, i), CELL=np.full(m, ci),
                      OFF=base + np.arange(m) * 3 * vs, VS=np.full(m, vs)))
    return _pack(L)


def load_rooms(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'SHG1', 'не SHG1'
    n, = struct.unpack_from('<I', b, 4); out = {}
    for k in range(n):
        name, off, size = struct.unpack_from('<32sII', b, 16 + 48 * k); name = name.split(b'\0')[0].decode()
        ntex, npc, toff, roff = struct.unpack_from('<4I', b, off + 4)
        L = []
        for i in range(npc):
            rec = struct.unpack_from('<6fiIIII3ffIII2I', b, off + roff + 80 * i)
            tex, fl, nv, ni = rec[6:10]; ox, oy, oz, sc = rec[11:15]; voff = rec[15]
            if ni == 0 or not fl & F_NOIDX: continue
            p, uv, vs = _tris(b, off + voff, fl, ni, sc, (ox, oy, oz)); m = len(p)
            L.append(dict(P=p, UV=uv, TEX=np.full(m, tex), FL=np.full(m, fl), PI=np.full(m, i), CELL=np.zeros(m),
                          OFF=off + voff + np.arange(m) * 3 * vs, VS=np.full(m, vs)))
        out[name] = _pack(L)
    return out


def room_flags(path):
    """комнаты SHG1 -> {имя: ИЛИ флагов всех кусков} (флаг 128 — обход проверен, рисовать с отсечением, tools/interior_export.py)"""
    b = Path(path).read_bytes(); assert b[:4] == b'SHG1'
    n, = struct.unpack_from('<I', b, 4); out = {}
    for k in range(n):
        name, off, size = struct.unpack_from('<32sII', b, 16 + 48 * k); name = name.split(b'\0')[0].decode()
        ntex, npc, toff, roff = struct.unpack_from('<4I', b, off + 4); f = 0
        for i in range(npc): f |= struct.unpack_from('<I', b, off + roff + 80 * i + 28)[0]
        out[name] = f
    return out
