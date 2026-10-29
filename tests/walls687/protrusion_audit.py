"""№687: выступает ли коллизия (отрезки-заборы COL1 и боковые грани ящиков) за видимую грань стены. Для каждой грани длиной >= 6 м:
точки через 1,5 м; в 1,5 м вдоль нормали ищем видимую вертикальную грань (|ny|<0.3), смотрящую в ту же сторону; p = на сколько коллизия ближе к проезду, чем видимая
стена (>0 — коллизия торчит в полосу). Итог по грани: медиана p и доля точек без видимой стены."""
import sys, struct, math, collections
sys.path.insert(0, 'tools')
import numpy as np, shr7read
lv = sys.argv[1]; b = open(lv, 'rb').read(); d = shr7read.load(lv)
co, po, pv = struct.unpack_from('<III', b, 92)[0], struct.unpack_from('<I', b, 96)[0], struct.unpack_from('<I', b, 88)[0]
h = struct.unpack_from('<4s3f8I', b, co); ntri, nbox, ncyl, nseg = h[6], h[7], h[8], h[9]; o = co + 48
o += ntri * 48; boxes = np.frombuffer(b, '<f4', nbox * 16, o).reshape(nbox, 16); o += nbox * 64; o += ncyl * 48
segs = np.frombuffer(b, '<f4', nseg * 8, o).reshape(nseg, 8)
P = d['P']; n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); l = np.linalg.norm(n, axis=1) + 1e-12; n = n / l[:, None]
m = (np.abs(n[:, 1]) < 0.3) & (l > 0.05)
V = P[m]; VN = n[m]; VC = V.mean(axis=1); print('вертикальных видимых треугольников', len(V), file=sys.stderr)
G = collections.defaultdict(list)
for i, c in enumerate(VC): G[(int(c[0] // 6), int(c[2] // 6))].append(i)
def vis_at(x, z, nx, nz, y0, y1):
    best = None
    for gx in range(int(x // 6) - 1, int(x // 6) + 2):
        for gz in range(int(z // 6) - 1, int(z // 6) + 2):
            for i in G.get((gx, gz), ()):
                vn = VN[i]; 
                if vn[0] * nx + vn[2] * nz < 0.85: continue
                p = V[i]
                if p[:, 1].max() < y0 or p[:, 1].min() > y1: continue
                off = (p[0, 0] - x) * nx + (p[0, 2] - z) * nz   # плоскость видимой грани впереди (+) или позади (-) точки по нормали (в сторону проезда)
                if abs(off) > 1.6: continue
                # точка (x,z) внутри горизонтального охвата треугольника вдоль касательной
                tx, tz = -nz, nx; t = (p[:, 0] - x) * tx + (p[:, 2] - z) * tz
                if t.min() - 0.3 > 0 or t.max() + 0.3 < 0: continue
                if best is None or abs(off) < abs(best): best = off
    return best
faces = []
for i, S in enumerate(segs):
    dx, dz = S[2] - S[0], S[3] - S[1]; L = math.hypot(dx, dz)
    if L >= 6 and S[7] - S[6] > 1.2: faces.append(('seg', i, S[0], S[1], dx / L, dz / L, S[4], S[5], L, -1e9, 1e9))
for i, B in enumerate(boxes):
    c = B[0:3]; ax = [B[3:6], B[6:9], B[9:12]]; hh = B[12:15]
    if B[15] == 1.0: continue
    for a in range(3):
        if abs(ax[a][1]) > 0.1: continue
        for v in range(3):
            if v == a or abs(ax[v][1]) < 0.9: continue
            t = 3 - a - v; L = 2 * hh[t]; ht = 2 * hh[v]
            if L < 6 or ht < 1.2: continue
            for s in (-1, 1):
                nx, nz = ax[a][0] * s, ax[a][2] * s; ll = math.hypot(nx, nz); nx /= ll; nz /= ll
                cx, cz = c[0] + nx * hh[a] * ll, c[2] + nz * hh[a] * ll; tx, tz = ax[t][0], ax[t][2]
                faces.append(('box', i, cx - tx * L / 2, cz - tz * L / 2, tx, tz, nx, nz, L, c[1] - ht / 2, c[1] + ht / 2))
rows = []
for f in faces:
    kind, i, ax_, az_, tx, tz, nx, nz, L, y0, y1 = f
    ps = []; none = 0; k = max(2, int(L // 1.5))
    for j in range(k):
        s = (j + .5) / k * L; x = ax_ + tx * s; z = az_ + tz * s
        off = vis_at(x, z, nx, nz, y0 if kind == 'box' else -1e9, y1 if kind == 'box' else 1e9)
        if off is None: none += 1
        else: ps.append(-off)   # off>0: видимая грань дальше от стены по нормали (в проезде) => коллизия ЗА видимой гранью (внутри); p = -off: >0 — коллизия торчит
    rows.append((kind, i, ax_ + tx * L / 2, az_ + tz * L / 2, L, none / k, float(np.median(ps)) if ps else None, float(np.max(ps)) if ps else None))
out = sys.argv[2]
with open(out, 'w') as fo:
    fo.write('kind\tidx\tcx\tcz\tlen\tдоля_без_видимой\tмедиана_p\tmax_p\n')
    for r in rows: fo.write('\t'.join('' if x is None else (f'{x:.2f}' if isinstance(x, float) else str(x)) for x in r) + '\n')
pr = [r for r in rows if r[6] is not None and r[6] > 0.15]; gh = [r for r in rows if r[5] > 0.6]
print(f'граней {len(rows)}; коллизия торчит > 15 см (медиана): {len(pr)}; без видимой стены (> 60 % точек): {len(gh)}')
