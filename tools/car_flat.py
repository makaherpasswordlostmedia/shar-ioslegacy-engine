#!/usr/bin/env python3
"""№930 «Машины NPC без текстур в мультике»: разбор текстур машин трафика (traffic.shr, TRF1) по моделям и кускам на Маке.

  python3 tools/car_flat.py traffic.shr [--table]
  python3 tools/car_flat.py msncars-lN.shr --sidecar carflatm930.bin  # то же для пакета машин миссий (MCR1): по модели — имя, число кусков, подпись, записи
  python3 tools/car_flat.py traffic.shr --sidecar carflat930.bin     # боковой файл для движка (viewer/carfill930.h, ступень 2): по куску — перестановка треугольников (заливка вперёд, рисунок в хвост) и цвет каждого треугольника заливки

По каждой текстуре пакета — решение тем же разбором, что у стен города (tools/flat_list.py classify): заливка (тон; перелив — цвет вершин, запечённая светотень) или текстура
(рисунок: фары, решётки, надписи, колёса, прозрачность). Кусок с флагом полупрозрачности, сложения, неба и кусок на текстуре, которую делят с таким куском, заливкой не идёт."""
import os, struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flat_list as F

QSZ = {'w': 0}


def load_trf(path):
    f = Path(path).read_bytes(); assert f[:4] == b'TRF1'
    u = struct.unpack_from('<' + 'I' * 40, f, 12)
    nModel, offModel, nPiece, offPiece, vertOff, vertBytes, nTex, offTex, texBytes = u[8], u[9], u[10], u[11], u[12], u[13], u[14], u[15], u[16]
    tex = []; p = offTex; end = offTex + texBytes
    for k in range(nTex):
        w, h, lv = struct.unpack_from('<HHH', f, p); t4 = f[p + 6] == 4; pre = f[p + 7] == 1
        pal = np.frombuffer(f, np.uint8, 1024, p + 16).reshape(256, 4); q = p + 16 + 1024; l0 = None; lw, lh = w, h; nbytes0 = 0
        for l in range(lv):
            rb = max(16, (lw + 1) >> 1) if t4 else (16 if (pre and lw < 16) else lw); rows = ((lh + 7) & ~7) if pre else lh
            if l == 0: l0 = (q, rb, rows)
            q += rb * rows; q = (q + 15) & ~15; lw = lw >> 1 or 1; lh = lh >> 1 or 1
        tex.append(dict(w=w, h=h, t4=t4, pre=pre, ground=False, pal=pal, l0=l0, bytes=q - p)); p = q
    models = []
    for m in range(nModel):
        b = f[offModel + 128 * m: offModel + 128 * m + 128]
        name = b[:16].split(b'\0')[0].decode('latin1'); fp, npc_, fl, nl = struct.unpack_from('<4H', b, 16)
        models.append(dict(name=name, first=fp, n=npc_, firstLod=fl, nLod=nl))
    pieces = []
    for i in range(nPiece):
        r = struct.unpack_from('<6fiiiii4f5I', f, offPiece + 80 * i)
        pieces.append(dict(tex=r[6], flags=r[7], nv=r[8], ni=r[9], owner=r[10], off=r[15], abs=vertOff + r[15], wheel=r[18], lod=r[19], geo=r[11:15]))
    return f, tex, models, pieces, (vertOff, vertBytes)


FAR_D, FAR_MAX = 45.0, 0.03   # №930: область текстуры, которую занимает кусок (по его UV), ровная, если точек дальше 45 от тона не больше 3 %


def piece_texels(f, vo, p, t):
    """-> массив индексов палитры текстур, на которые ложатся треугольники куска (UV: число/256 повторов, texel = uv * размер; кусок без индексов, вершины по 12 или 16 байт)"""
    if not (p['flags'] & 16) or p['ni'] <= 0: return None
    vs = 12 if p['flags'] & 32 else 16; n = p['ni'] // 3 * 3
    a = np.frombuffer(f, np.dtype('<u2'), n * vs // 2, p['abs']).reshape(n, vs // 2)
    uv = a[:, :2].astype(np.float64) / 256.0 * np.array([t['w'], t['h']])
    px = F.indices(f, t); h, w = px.shape; out = []
    for k in range(0, n, 3):
        tri = uv[k:k + 3]; lo = np.floor(tri.min(0) - .5).astype(int); hi = np.ceil(tri.max(0) + .5).astype(int)
        if (hi - lo).max() > 4 * max(w, h): return None   # развёртка на многие повторы: не атлас
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1)); cx, cy = xs + .5, ys + .5
        (ax, ay), (bx, by), (qx, qy) = tri; d = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
        if abs(d) < 1e-9: m = (np.abs(cx - tri[:, 0].mean()) <= .5 + 1e-9) & (np.abs(cy - tri[:, 1].mean()) <= .5 + 1e-9)
        else:
            w1 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / d; w2 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / d; w3 = 1 - w1 - w2
            e = .5 / max(1.0, abs(d) ** .5)   # запас на полтекселя
            m = (w1 >= -e) & (w2 >= -e) & (w3 >= -e)
        out.append(px[ys[m] % h, xs[m] % w])
        if not m.any(): out.append(px[[int(tri[:, 1].mean()) % h], [int(tri[:, 0].mean()) % w]])
    return np.concatenate(out) if out else None


def region_decide(t, idx):
    """-> (заливка?, тон RGB, доля тона, доля дальних) по множеству точек куска"""
    pal = t['pal']; cnt = np.bincount(idx, minlength=256); alpha = pal[:, 3]; tot = int(cnt[alpha >= 16].sum())
    if not tot or (cnt.sum() - tot) * 50 > cnt.sum(): return False, (0, 0, 0), 0., 1.
    c = F.cluster(pal, cnt)
    if c is None: return False, (0, 0, 0), 0., 1.
    w1, col = c; d = np.sqrt(((pal[:, :3].astype(float) - col) ** 2).sum(axis=1)); far = float(cnt[(d > FAR_D) & (alpha >= 16)].sum()) / tot
    return far <= FAR_MAX, tuple(int(round(x)) for x in col), w1 / tot, far


def tri_texels(t, px, uv3):
    h, w = px.shape; tri = uv3 * np.array([t['w'], t['h']])
    lo = np.floor(tri.min(0) - .5).astype(int); hi = np.ceil(tri.max(0) + .5).astype(int)
    if (hi - lo).max() > 4 * max(w, h): return None
    xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1)); cx, cy = xs + .5, ys + .5
    (ax, ay), (bx, by), (qx, qy) = tri; d = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
    if abs(d) < 1e-9: m = (np.abs(cx - tri[:, 0].mean()) <= .5 + 1e-9) & (np.abs(cy - tri[:, 1].mean()) <= .5 + 1e-9)
    else:
        w1 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / d; w2 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / d; w3 = 1 - w1 - w2; e = .5 / max(1.0, abs(d) ** .5)
        m = (w1 >= -e) & (w2 >= -e) & (w3 >= -e)
    r = px[ys[m] % h, xs[m] % w]
    return r if r.size else px[[int(tri[:, 1].mean()) % h], [int(tri[:, 0].mean()) % w]]


ERR_MAX, SPLIT_MIN, TAIL_MIN, TAIL_PCT = float(os.environ.get('CARFLAT_ERR', 30.0)), 0.40, 4, 0.04   # №971: 30 (было 14, CARFLAT_ERR=14 — как в TEST66): рисунок в хвосте куска 12 % -> 7 %   # ступень 2: треугольник идёт заливкой, если цвета его трёх вершин (взятые с текстуры в точках вершин) с переливом по треугольнику (Гуро) отличаются от текстуры по всей области в среднем не больше 14 (RGB); кусок идёт, если заливкой ≥ 40 % его треугольников; хвост с рисунком не больше 4 треугольников или 4 % куска заливается вместе (второй вызов дороже)
PIECE_EXCL = 1 | 2 | 4 | (1 << 24) | (1 << 26)
import os
ONLY = {int(x) for x in os.environ['CARFLAT_ONLY'].split(',')} if os.environ.get('CARFLAT_ONLY') else None   # служебно: только эти куски (разбор «что даёт грани»)


# №956 (Роб 25.10: «машины NPC из серых в интересные тона гаммы Симпсонов, палитра №825»): у кусков кузова средне-серой краски (насыщенность < 0,12, яркость 0,30–0,72, не колесо, ≥ 90 треугольников)
# цвета вершин заменяются на тон палитры Springfield (ggsci, ресёрч №825) с сохранением светотени краски (отношение серого вершины к среднему куска); тон — по хэшу имени модели, у модели один и тот же.
# Белое, чёрное, полицейские, скорая, пожарные, ритуальные и броневик остаются как есть. CARFLAT_RECOLOR_OLD=1 — без перекраски (как №930)
PAL956 = [(0xF0, 0x5C, 0x3B), (0xFD, 0x74, 0x46), (0x46, 0x73, 0x2E), (0x19, 0x7E, 0xC0), (0x1A, 0x99, 0x93)]   # светло-голубой и бледно-зелёный палитры не берём: на машине читаются неоном
KEEP956 = __import__('re').compile(r'police|ambul|husk|hears|limo|armor|fire|plow|garbage|nuc|ship|coffin|hallo|zombi|wreck', __import__('re').I)
RECOLOR = os.environ.get('CARFLAT_RECOLOR_OLD') != '1'
def recolor956(name, wheel, cl):
    """цвета вершин куска (список (R, G, B)) -> те же, перекрашенные в тон палитры, или тот же список, если кусок не серая краска"""
    if not RECOLOR or wheel or not name or KEEP956.search(name) or len(cl) < 270: return cl
    a = np.array(cl, float) / 255.; mx = a.max(1); mn = a.min(1); s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.)
    if not (s.mean() < .12 and .30 <= mx.mean() <= .72): return cl
    g = a.mean(1); k = np.clip(g / max(float(g.mean()), 1e-3), .6, 1.5)
    h = 2166136261
    for ch in name.encode('latin1'): h = ((h ^ ch) * 16777619) & 0xffffffff
    pr = np.array(PAL956[h % len(PAL956)], float)
    out = np.clip(pr[None, :] / pr.max() * 255. * .62 * k[:, None], 0, 255)   # яркость кузова около 0,62 (было серое 0,3–0,7), светотень краски сохранена
    return [tuple(int(round(x)) for x in c) for c in out]


def tri_gouraud(t, px, uv3):
    """-> None (развёртка на многие повторы или прозрачные точки) или (ошибка, [(R, G, B) × 3]): цвет каждой вершины — текстура в точке вершины (чуть внутрь треугольника), ошибка — среднее по текселям области расстояние между текстурой и переливом цветов вершин"""
    h, w = px.shape; tri = uv3 * np.array([t['w'], t['h']]); pal = t['pal']
    lo = np.floor(tri.min(0) - .5).astype(int); hi = np.ceil(tri.max(0) + .5).astype(int)
    if (hi - lo).max() > 4 * max(w, h): return None
    xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1)); cx, cy = xs + .5, ys + .5
    (ax, ay), (bx, by), (qx, qy) = tri; d = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy); cen = tri.mean(0)
    if abs(d) < 1e-9:
        m = (np.abs(cx - cen[0]) <= .5 + 1e-9) & (np.abs(cy - cen[1]) <= .5 + 1e-9); W = np.full((int(m.sum()), 3), 1 / 3.)
    else:
        w1 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / d; w2 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / d; w3 = 1 - w1 - w2; e = .5 / max(1.0, abs(d) ** .5)
        m = (w1 >= -e) & (w2 >= -e) & (w3 >= -e); W = np.stack([w1[m], w2[m], w3[m]], 1)
    if not m.any(): g = np.abs(cx - cen[0]) + np.abs(cy - cen[1]); m = np.zeros_like(m); m[np.unravel_index(np.argmin(g), g.shape)] = True; W = np.full((1, 3), 1 / 3.)
    idx = px[ys[m] % h, xs[m] % w]
    if (pal[idx, 3] < 16).any(): return None
    tex = pal[idx, :3].astype(float); cols = []
    for k in range(3):
        v = tri[k]; dv = cen - v; L = float(np.hypot(*dv)); pt = v + dv * min(1.0, .75 / L) if L > 1e-9 else v
        cols.append(pal[px[int(np.floor(pt[1])) % h, int(np.floor(pt[0])) % w], :3].astype(float))
    C = np.array(cols); err = float(np.sqrt(((tex - W @ C) ** 2).sum(1)).mean())
    return err, [tuple(int(round(x)) for x in c) for c in C]


def piece_split(f, t, p):
    """-> None (кусок остаётся с текстурой целиком) или (K, перестановка треугольников [заливка..., рисунок...], цвета вершин (R, G, B) × 3K первых K треугольников до цветокоррекции мультика):
    треугольники с ровной областью текстуры — заливкой цветами вершин (перелив Гуро, без граней), с рисунком (фары, решётки, номер, швы) — остаются текстурой в хвосте куска"""
    if p['tex'] < 0 or not (p['flags'] & 16) or p['ni'] <= 0 or (p['flags'] & PIECE_EXCL) or p['owner'] == 3: return None
    px = F.indices(f, t); vs = 12 if p['flags'] & 32 else 16; n = p['ni'] // 3 * 3
    a = np.frombuffer(f, np.dtype('<u2'), n * vs // 2, p['abs']).reshape(n, vs // 2); uv = a[:, :2].astype(float) / 256.
    flat = []; det = []; col = {}; allc = {}
    for k in range(0, n, 3):
        i = k // 3; r = tri_gouraud(t, px, uv[k:k + 3])
        if r is not None: allc[i] = r[1]
        if r is not None and r[0] <= ERR_MAX: flat.append(i); col[i] = r[1]
        else: det.append(i)
    tris = n // 3
    if det and len(det) <= max(TAIL_MIN, TAIL_PCT * tris) and all(i in allc for i in det):   # рисунок в паре треугольников (точка на образце краски): не стоит второго вызова — заливка всем куском
        flat = sorted(flat + det); col.update({i: allc[i] for i in det}); det = []
    if not flat or len(flat) < SPLIT_MIN * tris or (p['wheel'] and det): return None   # колесо — только целиком заливкой (остов huskA); со ступицей остаётся текстурой
    cl = [c for i in flat for c in col[i]]
    if os.environ.get('CARFLAT_MARK'): cl = [(255, 0, 0) if c[0] < 70 else (255, 255, 255) for c in cl]   # служебно: тёмные тона красным, остальное белым
    return len(flat), flat + det, cl



# №972 (Роб 25.10: «у машин NPC колёса и днище просвечивают цветом кузова, а не чёрным, издалека очень заметно»): причина — recolor956 поджимал яркость треугольника снизу (k >= 0,6), и тёмные части куска кузова
# (арки колёс, днище, шины в дальней версии, где колёса слиты с кузовом) получали тон кузова на 60 %. Теперь треугольник заливки, который в оригинале тёмный (серое < DARK_T и темнее 0,85 среднего куска) или смотрит вниз
# (днище, внутренность арки, нижняя кромка бампера), красится нейтральным почти чёрным: оригинальный цвет × DARK_MUL, не выше DARK_CAP. У колёсных кусков (wheel != 0) темнеет только шина (серое < DARK_T); остов huskA и полицейские, скорая и т. п. по списку KEEP956 перекраске не подлежат, но тёмный низ у них тот же. CARFLAT_DARK972_OLD=1 — как до правки
DARK_T, DARK_REL, DARK_MUL, DARK_CAP, DOWN_NY, DOWN_H = 0.28, 0.85, 0.35, 36, -0.35, 0.5
DARK972 = os.environ.get('CARFLAT_DARK972_OLD') != '1'


def tri_positions(f, p):
    """-> (ntri, 3, 3) координаты вершин куска (модель), как в движке: o + sc / 32768 * int16"""
    vs = 12 if p['flags'] & 32 else 16; xo = 6 if vs == 12 else 8; n = p['ni'] // 3 * 3
    raw = np.frombuffer(f, np.uint8, n * vs, p['abs']).reshape(n, vs)
    xyz = np.stack([np.frombuffer(raw[:, xo + 2 * k: xo + 2 * k + 2].tobytes(), '<i2') for k in range(3)], 1).astype(float)
    ox, oy, oz, sc = p['geo']
    return (np.array([ox, oy, oz]) + sc / 32768. * xyz).reshape(-1, 3, 3)


def down_faces(f, p):
    """-> bool на каждый треугольник куска: смотрит вниз (знак нормали сверяется по самым верхним горизонтальным граням куска; обход вершин у данных зеркальный, поэтому знак берётся по куску)"""
    P = tri_positions(f, p); N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); L = np.linalg.norm(N, axis=1); N = N / np.maximum(L[:, None], 1e-9)
    y = P[:, :, 1].mean(1); top = (y >= np.percentile(y, 90)) & (np.abs(N[:, 1]) > .8) & (L > 1e-9)
    s = float(np.sign(np.median(N[top, 1]))) if top.any() else 1.
    return ((N[:, 1] * (s or 1.)) < DOWN_NY) & (y < y.min() + DOWN_H * (y.max() - y.min()))   # только нижняя часть куска: козырёк и стойки у крыши тоже смотрят вниз, но это не днище


def darken972(f, p, perm, K, src, cols):
    """src — цвета вершин заливки до №956, cols — после; -> cols, где тёмные и нижние треугольники заливки нейтрально почти чёрные"""
    if not DARK972 or p.get('geo') is None: return cols
    a = np.array(src, float).reshape(-1, 3, 3) / 255.; g = a.mean((1, 2)); mean = float(g.mean())
    if p['wheel']: dark = g < DARK_T   # колесо: шина (тёмная) — почти чёрная, ступица остаётся
    else:
        ay = tri_positions(f, p)[:, :, 1].mean(1); low = (ay < ay.min() + DOWN_H * (ay.max() - ay.min()))[np.array(perm[:K])]   # нижняя часть куска: у крыши и капота тёмные полосы (рамка стекла, козырёк) — не днище
        dark = (((g < DARK_T) & (g < DARK_REL * mean)) & low) | down_faces(f, p)[np.array(perm[:K])]
    if not dark.any(): return cols
    out = np.array(cols, float).reshape(-1, 3, 3)
    d = np.minimum(np.array(src, float).reshape(-1, 3, 3) * DARK_MUL, DARK_CAP)
    out[dark] = d[dark]
    return [tuple(int(round(x)) for x in c) for c in out.reshape(-1, 3)]



def split_records(f, tex, pieces, names=None):
    import struct as S
    body = bytearray(); cnt = 0
    for j, p in enumerate(pieces):
        if p['tex'] < 0 or (ONLY is not None and j not in ONLY): continue
        r = piece_split(f, tex[p['tex']], p)
        if r is None: continue
        K, perm, cols = r; ntri = p['ni'] // 3
        src = cols; cols = recolor956(names[j] if names else None, p['wheel'], cols)   # №956
        cols = darken972(f, p, perm, K, src, cols)   # №972
        rec = S.pack('<III', j, ntri, K) + b''.join(bytes(c) for c in cols)
        if K < ntri: rec += S.pack('<%dH' % ntri, *perm)
        rec += b'\0' * (-len(rec) % 4); body += rec; cnt += 1   # запись кратна 4 Б: движок читает слова без невыровненного доступа
    return bytes(body), cnt


def sig_of(pieces):
    sig = 2166136261
    for p in pieces:
        for v in (p['tex'] & 0xffffffff, p['ni'], p['flags']): sig = ((sig ^ v) * 16777619) & 0xffffffff
    return sig


def sidecar(f, tex, pieces, out, names=None):
    import struct as S
    body, cnt = split_records(f, tex, pieces, names)
    Path(out).write_bytes(b'CFL2' + S.pack('<III', len(pieces), sig_of(pieces), cnt) + body); return cnt


def sidecar_mcr(path, out):
    """CFM2: 'CFM2', число моделей, по модели 36 Б: имя[16], число кусков, подпись, число записей, смещение блока, размер блока; потом блоки (движок читает только блок своей модели)"""
    import struct as S
    blocks = []; tot = 0
    for name, f, tex, pieces in load_mcr(path):
        body, cnt = split_records(f, tex, pieces, [name] * len(pieces)); blocks.append((name, len(pieces), sig_of(pieces), cnt, body)); tot += cnt
    off = 8 + 36 * len(blocks); d = bytearray(b'CFM2' + S.pack('<I', len(blocks))); data = bytearray()
    for name, npc_, sig, cnt, body in blocks:
        d += S.pack('<16sIIIII', name.encode('latin1')[:15], npc_, sig, cnt, off + len(data), len(body)); data += body
    Path(out).write_bytes(bytes(d) + bytes(data)); return len(blocks), tot


def decide(f, tex, pieces, notoon=()):
    """-> по текстуре (вид, причина, тон, доля, границы); кусок с полупрозрачностью, сложением, небом, куском-владельцем 'не машина' делает текстуру нерешаемой"""
    bad = set()
    for p in pieces:
        if p['tex'] >= 0 and (p['flags'] & (1 | 2 | 4 | (1 << 24))): bad.add(p['tex'])
    res = []
    for i, t in enumerate(tex):
        k, why, col, sh, ed = F.classify(f, t, i in notoon)
        if k and i in bad: k, why = 0, 11   # 11 — делится с полупрозрачным куском
        res.append((k, why, col, sh, ed))
    return res


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')][:1]
    if '--sidecar' in sys.argv and Path(a[0]).read_bytes()[:4] == b'MCR1':
        out = sys.argv[sys.argv.index('--sidecar') + 1]; nm, tot = sidecar_mcr(a[0], out); print(f'{a[0]}: моделей {nm}, кусков с заливкой {tot} -> {out}'); return
    f, tex, models, pieces, _ = load_trf(a[0])
    if '--sidecar' in sys.argv:
        out = sys.argv[sys.argv.index('--sidecar') + 1]; nm_ = [''] * len(pieces)
        for m_ in models: nm_[m_['first']:m_['first'] + m_['n']] = [m_['name']] * m_['n']
        for m_ in models: nm_[m_['firstLod']:m_['firstLod'] + m_['nLod']] = [m_['name']] * m_['nLod']   # №956: дальние версии той же модели — тот же тон
        n = sidecar(f, tex, pieces, out, nm_); print(f'{a[0]}: кусков с заливкой {n} из {len(pieces)} -> {out}'); return
    res = decide(f, tex, pieces)
    kb = sum(t['bytes'] for t in tex); fb = sum(t['bytes'] for t, r in zip(tex, res) if r[0])
    print(f'{a[0]}: текстур {len(tex)} ({kb // 1024} КБ), заливка {sum(r[0] for r in res)} ({fb // 1024} КБ), моделей {len(models)}, кусков {len(pieces)}')
    if '--table' in sys.argv:
        for m in models:
            ps = pieces[m['first']: m['first'] + m['n']]
            rows = []
            for j, p in enumerate(ps):
                t = p['tex']; r = res[t] if t >= 0 else None
                rows.append(f"    кусок {m['first'] + j:4d} колесо={p['wheel']} флаги={p['flags']:#x} треуг={p['ni'] // 3:4d} текстура={t:3d} " + ('нет' if r is None else ('заливка %s' % (tuple(r[2]),) if r[0] else f'текстура (причина {r[1]})')))
            nf = sum(1 for p in ps if p['tex'] >= 0 and res[p['tex']][0])
            print(f"  {m['name']:12s} кусков {m['n']:3d}, заливкой {nf}"); print('\n'.join(rows))



def load_mcr(path):
    """пакет msncars (MCR1) -> [(имя, f, tex, pieces)]: у каждой модели блок со своими текстурами и кусками (смещения вершин и пикселей абсолютные)"""
    f = Path(path).read_bytes(); assert f[:4] == b'MCR1'
    _, ver, lvl, n, dirOff = struct.unpack_from('<4sIIII', f, 0)[0:5]
    out = []
    for m in range(n):
        d = dirOff + 176 * m; name = f[d:d + 16].split(b'\0')[0].decode('latin1'); u = struct.unpack_from('<8I', f, d + 144)
        blk, size, npc_, vOff, vBytes, tOff, tBytes, nTex = u
        tex = []; p = blk + tOff
        for k in range(nTex):
            w, h, lv = struct.unpack_from('<HHH', f, p); t4 = f[p + 6] == 4; pre = f[p + 7] == 1
            pal = np.frombuffer(f, np.uint8, 1024, p + 16).reshape(256, 4); q = p + 16 + 1024; l0 = None; lw, lh = w, h
            for l in range(lv):
                rb = max(16, (lw + 1) >> 1) if t4 else (16 if (pre and lw < 16) else lw); rows = ((lh + 7) & ~7) if pre else lh
                if l == 0: l0 = (q, rb, rows)
                q += rb * rows; q = (q + 15) & ~15; lw = lw >> 1 or 1; lh = lh >> 1 or 1
            tex.append(dict(w=w, h=h, t4=t4, pre=pre, ground=False, pal=pal, l0=l0, bytes=q - p)); p = q
        pieces = []
        for i in range(npc_):
            r = struct.unpack_from('<6fiiiii4f5I', f, blk + 80 * i)
            pieces.append(dict(tex=r[6], flags=r[7], nv=r[8], ni=r[9], owner=r[10], off=r[15], abs=blk + vOff + r[15], wheel=r[18], lod=r[19], geo=r[11:15]))
        out.append((name, f, tex, pieces))
    return out


if __name__ == '__main__':
    main()
