#!/usr/bin/env python3
"""№983 «кромка тротуара у дороги» и «контур тропинок» (Роб 25.10): куски города рисуются по текстурам, а кромка у дороги лежит в тех же больших кусках, что и верх тротуара, поэтому по цвету её не отделить.
Мак выбирает крайние треугольники тротуара (вершина ближе EDGE_D к вершине асфальта) и пишет edge983.bin рядом с level.shr: треугольники с цветом света вершин, по клеткам 64 м (как toonlines.shr);
движок рисует их слоем поверх тротуара заливкой бордюра (серо-фиолетовый, №974). Второй файл — pathlines983.shr (формат TLN2): отрезки файла линий мира, лежащие на краях тротуаров и тропинок
(те же текстуры); движок рисует их пером тёмного насыщенного тона тротуара (№978), поверх чёрных линий мира.

  python3 tools/edge983_list.py level.shr [toonlines.shr] [edge983.bin] [pathlines983.shr]

Формат EG83: 'EG83', ncell u32, nvert u32, подпись u32 (FNV-1a по номерам текстур кусков, как у flat912.bin); ncell × {cx i16, cz i16, first u32, count u32} (count — вершины, по 3 на треугольник);
nvert × 12 байт {цвет RGBA 4 байта как у вершины куска, x, y, z i16 в сантиметрах от угла клетки (cx·64, 0, cz·64), 0 u16}. Файл линий: TLN2 ('TLN2', ncell, nline; те же клетки; 12 байт на линию)."""
import struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flat_list as F
import shr7read as S

CELL = 64.0
EDGE_D = 0.45      # вершина тротуара ближе к вершине асфальта (по плану), м
EDGE_DY = 0.6      # и по высоте не дальше, м
LINE_D = 0.2       # линия лежит на ребре тротуара: середина ближе к ребру, м
LINE_COS = 0.93
THIN_H = 0.8       # только узкие треугольники (высота от длинной стороны, м): широкий клин у дороги остаётся цветом тротуара, красить его целиком некрасиво


def walk_class(tone):
    r, g, b = tone; mx, mn = max(r, g, b), min(r, g, b)
    return (mx - mn <= 24) and (.299 * r + .587 * g + .114 * b >= 125)


def vcolors(b, d, k):
    """цвет света трёх вершин треугольников k (как у вершин куска, RGBA 8888); 16-бит цвет 5-6-5 расширяется"""
    out = np.zeros((len(k), 3, 4), np.uint8)
    for j in range(3):
        off = d['OFF'][k] + j * d['VS'][k]; vs = d['VS'][k]
        raw = np.frombuffer(b, np.uint8)
        is12 = vs == 12
        for n in range(len(k)):
            o = int(off[n])
            if is12[n]:
                c = int(raw[o + 4]) | int(raw[o + 5]) << 8; r = c & 31; g = (c >> 5) & 63; bl = c >> 11
                out[n, j] = (r * 255 // 31, g * 255 // 63, bl * 255 // 31, 255)
            else:
                out[n, j] = (raw[o + 4], raw[o + 5], raw[o + 6], 255)
    return out


def build(lvl, tl=None):
    f, tex, sig = F.load_level(lvl); rows = [F.classify(f, t, False) for t in tex]
    asph = F.asphalt_set(f, tex, rows)
    walk = {i for i, r in enumerate(rows) if r[0] == 1 and tex[i]['ground'] and walk_class(r[2]) and F.curb_class(f, tex[i]) != 1}
    d = S.load(lvl); P, T = d['P'], d['TEX']; b = Path(lvl).read_bytes()
    # вершины асфальта в сетку 1 м (xz)
    G = {}
    for k in np.where(np.isin(T, list(asph)))[0]:
        for j in range(3): G.setdefault((int(P[k, j, 0] // 1.0), int(P[k, j, 2] // 1.0)), []).append(P[k, j])
    def near_road(p):
        cx, cz = int(p[0] // 1.0), int(p[2] // 1.0)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for q in G.get((cx + i, cz + j), ()):
                    if (q[0] - p[0]) ** 2 + (q[2] - p[2]) ** 2 <= EDGE_D ** 2 and abs(q[1] - p[1]) <= EDGE_DY: return True
        return False
    edge = []
    for k in np.where(np.isin(T, list(walk)))[0]:
        if any(near_road(P[k, j]) for j in range(3)):
            e1, e2 = P[k, 1] - P[k, 0], P[k, 2] - P[k, 0]; area = np.linalg.norm(np.cross(e1, e2)) * .5; me = max(np.linalg.norm(e1), np.linalg.norm(e2), np.linalg.norm(P[k, 2] - P[k, 1]))
            if me > 1e-6 and 2 * area / me <= THIN_H: edge.append(int(k))
    edge = np.array(edge, int)
    col = vcolors(b, d, edge) if len(edge) else np.zeros((0, 3, 4), np.uint8)
    cells = {}
    for n, k in enumerate(edge):
        c = P[k].mean(0); cells.setdefault((int(c[0] // CELL), int(c[2] // CELL)), []).append(n)
    body = bytearray(); table = bytearray(); first = 0
    for (cx, cz), ns in sorted(cells.items()):
        for n in ns:
            k = edge[n]
            for j in range(3):
                x = int(round((P[k, j, 0] - cx * CELL) * 100)); y = int(round(P[k, j, 1] * 100)); z = int(round((P[k, j, 2] - cz * CELL) * 100))
                body += bytes(col[n, j]) + struct.pack('<hhhH', max(-32768, min(32767, x)), max(-32768, min(32767, y)), max(-32768, min(32767, z)), 0)
        table += struct.pack('<hhII', cx, cz, first, len(ns) * 3); first += len(ns) * 3
    eg = b'EG83' + struct.pack('<III', len(cells), first, sig) + bytes(table) + bytes(body)
    # линии тропинок: отрезки toonlines.shr на рёбрах треугольников тротуаров и тропинок
    pl = None; nlines = 0
    if tl and Path(tl).exists():
        tb = Path(tl).read_bytes(); assert tb[:4] == b'TLN2'
        nc, nv = struct.unpack_from('<II', tb, 4); cells_t = [struct.unpack_from('<hhII', tb, 12 + 12 * i) for i in range(nc)]
        vo = 12 + 12 * nc; V = np.frombuffer(tb, '<i2', nv * 6, vo).reshape(nv, 2, 3).astype(float)
        # рёбра тротуаров: выборка точек каждые 0,5 м в сетку 0,5 м
        wk = np.where(np.isin(T, list(walk)))[0]; E = {}
        segs = []
        for k in wk:
            for j in range(3):
                a, c2 = P[k, j], P[k, (j + 1) % 3]; segs.append((a, c2)); n = int(np.linalg.norm(c2 - a) / .5) + 1
                for s in range(n + 1):
                    p = a + (c2 - a) * s / n; E.setdefault((int(p[0] // .5), int(p[2] // .5)), []).append(len(segs) - 1)
        keep = []
        for ci, (cx, cz, first_, cnt) in enumerate(cells_t):
            for li in range(first_, first_ + cnt):
                a = V[li, 0] / 100.0 + [cx * CELL, 0, cz * CELL]; c2 = V[li, 1] / 100.0 + [cx * CELL, 0, cz * CELL]
                m = (a + c2) / 2; dv = c2 - a; ln = np.linalg.norm(dv)
                if ln < 0.3: continue
                dv /= ln; ok = False
                for i in (-1, 0, 1):
                    for j in (-1, 0, 1):
                        for si in set(E.get((int(m[0] // .5) + i, int(m[2] // .5) + j), ())):
                            sa, sb = segs[si]; sv = sb - sa; sl = np.linalg.norm(sv)
                            if sl < 1e-6 or abs(float(dv @ (sv / sl))) < LINE_COS: continue
                            t = float(np.clip((m - sa) @ sv / (sl * sl), 0, 1)); q = sa + sv * t
                            if np.linalg.norm(q - m) <= LINE_D: ok = True; break
                        if ok: break
                    if ok: break
                if ok: keep.append((ci, li))
        nlines = len(keep); cellsk = {}
        for ci, li in keep: cellsk.setdefault(ci, []).append(li)
        tab2 = bytearray(); body2 = bytearray(); first2 = 0
        for ci in sorted(cellsk):
            cx, cz = cells_t[ci][0], cells_t[ci][1]
            for li in cellsk[ci]: body2 += V[li].astype('<i2').tobytes()
            tab2 += struct.pack('<hhII', cx, cz, first2, len(cellsk[ci])); first2 += len(cellsk[ci])
        pl = b'TLN2' + struct.pack('<II', len(cellsk), first2) + bytes(tab2) + bytes(body2)
    return eg, len(edge), pl, nlines, len(walk), len(asph)


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else ''   # edge — только edge983.bin, path — только pathlines983.shr (правила ship_rules.txt, tools/check_sidecars.py)
    a = [x for i, x in enumerate(sys.argv[1:], 1) if not x.startswith('--') and sys.argv[i - 1] != '--only']
    lvl = Path(a[0]); tl = a[1] if len(a) > 1 else str(lvl.with_name('toonlines.shr'))
    out = a[2] if len(a) > 2 else str(lvl.with_name('edge983.bin')); outl = a[3] if len(a) > 3 else str(lvl.with_name('pathlines983.shr'))
    if only == 'path': out, outl = '/dev/null', out
    eg, n, pl, nl, nw, na = build(str(lvl), tl)
    if only != 'path': Path(out).write_bytes(eg)
    if pl and only != 'edge': Path(outl).write_bytes(pl)
    print(f'{lvl}: треугольников кромки {n} (текстур тротуара {nw}, асфальта {na}), линий тропинок {nl} -> {out}')


if __name__ == '__main__':
    main()
