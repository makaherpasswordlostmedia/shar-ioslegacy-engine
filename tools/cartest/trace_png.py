"""Картинки трасс cartest: вид сверху на коллизию COL1 вокруг трассы + путь машины.
python tools/cartest/trace_png.py LEVEL.shr DIR/traces.bin OUTDIR [--px 4] [--all]
Земля — серый по высоте (крутая — красный), ящики — синие, цилиндры/капсулы — зелёные, заборы — жёлтые с засечкой
нормали. Путь: цвет по скорости (синий медленно -> белый 30 м/с), в воздухе — голубой; метки: X красный — провал /
нет земли, пурпурный — выезд за забор, оранжевый квадрат — застрял, бирюзовый круг — возврат на надёжное место,
жёлтая точка — проникновение > 5 см, мелкий красный — отменённый подшаг. Старт — зелёный круг."""
import sys, struct, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from col_check import load, parse_col   # разбор SHR7/COL1 (tools/col_check.py)

F_FALL, F_EXIT, F_PEN, F_STUCK, F_REC, F_REV, F_AIR, F_HIT = 1, 2, 4, 8, 16, 32, 64, 128

def read_traces(p):
    b = Path(p).read_bytes(); assert b[:4] == b'TRC1'
    n, = struct.unpack_from('<i', b, 4); o = 8; out = []
    for _ in range(n):
        run, pt, mode, seed, cnt = struct.unpack_from('<5i', b, o); score, = struct.unpack_from('<f', b, o + 20); o += 24
        a = np.frombuffer(b, np.dtype([('x', '<f4'), ('z', '<f4'), ('y', '<f4'), ('v', '<f4'), ('fl', 'u1')]), cnt, o); o += cnt * 17
        out.append(dict(run=run, pt=pt, mode='wild' if mode else 'road', seed=seed, score=score, tp=a))
    return out

def render(C, tr, path, px=4.0, margin=25.0):
    tp = tr['tp']; x0, x1 = tp['x'].min() - margin, tp['x'].max() + margin; z0, z1 = tp['z'].min() - margin, tp['z'].max() + margin
    s = px; W, H = int((x1 - x0) * s) + 1, int((z1 - z0) * s) + 1
    if W * H > 16e6: s = (16e6 / ((x1 - x0) * (z1 - z0))) ** .5; W, H = int((x1 - x0) * s) + 1, int((z1 - z0) * s) + 1
    img = Image.new('RGB', (W, H), (18, 18, 22)); d = ImageDraw.Draw(img)
    P = lambda x, z: ((x - x0) * s, (z - z0) * s)
    T = C['tri']; cx = T[:, :3, 0].mean(1); cz = T[:, :3, 2].mean(1)
    m = (cx > x0 - 30) & (cx < x1 + 30) & (cz > z0 - 30) & (cz < z1 + 30)
    ys = T[m][:, :3, 1]; lo, hi = (np.percentile(ys, 2), np.percentile(ys, 98)) if m.any() else (0, 1)
    for t in T[m]:
        ny = t[3, 1]; g = int(50 + 150 * np.clip((t[:3, 1].mean() - lo) / max(hi - lo, 1e-3), 0, 1))
        col = (g, g, g) if ny > 0.5 else (170, 40, 40)
        d.polygon([P(t[k, 0], t[k, 2]) for k in range(3)], fill=col)
    B = C['box']
    for b in B:
        c = b[:3]; A = b[3:12].reshape(3, 3); h = b[12:15]
        if abs(c[0] - (x0 + x1) / 2) > (x1 - x0) / 2 + 60 or abs(c[2] - (z0 + z1) / 2) > (z1 - z0) / 2 + 60: continue
        pts = [c + A[0] * h[0] * sx + A[1] * h[1] * sy + A[2] * h[2] * sz for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        pts = np.array(pts)[:, [0, 2]]
        # выпуклая оболочка xz
        o = np.lexsort((pts[:, 1], pts[:, 0])); pts = pts[o]
        def cross(o_, a, b_): return (a[0] - o_[0]) * (b_[1] - o_[1]) - (a[1] - o_[1]) * (b_[0] - o_[0])
        lower, upper = [], []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
            lower.append(tuple(p))
        for p in pts[::-1]:
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
            upper.append(tuple(p))
        hull = lower[:-1] + upper[:-1]
        if len(hull) >= 3: d.polygon([P(*q) for q in hull], outline=(80, 140, 255))
    Y = C['cyl']
    for c in Y:
        if abs(c[0] - (x0 + x1) / 2) > (x1 - x0) / 2 + 30 or abs(c[2] - (z0 + z1) / 2) > (z1 - z0) / 2 + 30: continue
        a = c[3:6]; r = c[6]; hl = c[7]
        p0, p1 = c[:3] - a * hl, c[:3] + a * hl
        d.line([P(p0[0], p0[2]), P(p1[0], p1[2])], fill=(60, 200, 90), width=max(1, int(2 * r * s)))
        for q in (p0, p1): d.ellipse([P(q[0] - r, q[2] - r), P(q[0] + r, q[2] + r)], outline=(60, 200, 90))
    for g in C['seg']:
        ax, az, bx, bz, nx, nz = g[:6]
        d.line([P(ax, az), P(bx, bz)], fill=(240, 210, 40), width=2)
        mx, mz = (ax + bx) / 2, (az + bz) / 2; d.line([P(mx, mz), P(mx + nx * 1.5, mz + nz * 1.5)], fill=(240, 210, 40))
    # путь
    for i in range(1, len(tp)):
        a, b = tp[i - 1], tp[i]
        if b['fl'] & F_REC: continue
        k = int(np.clip(abs(b['v']) / 30, 0, 1) * 255)
        col = (120, 220, 255) if b['fl'] & F_AIR else (k, k, 255)
        d.line([P(a['x'], a['z']), P(b['x'], b['z'])], fill=col, width=2)
    sx, sz = tp[0]['x'], tp[0]['z']; d.ellipse([P(sx - 1.5, sz - 1.5), P(sx + 1.5, sz + 1.5)], outline=(40, 255, 40), width=2)
    for p in tp:
        x, z, fl = p['x'], p['z'], p['fl']
        if fl & F_REV: d.point(P(x, z), fill=(255, 60, 60))
        if fl & F_PEN: d.ellipse([P(x - .4, z - .4), P(x + .4, z + .4)], fill=(255, 240, 0))
        if fl & F_REC: d.ellipse([P(x - 1.2, z - 1.2), P(x + 1.2, z + 1.2)], outline=(0, 255, 220), width=2)
        if fl & F_STUCK: d.rectangle([P(x - 1.2, z - 1.2), P(x + 1.2, z + 1.2)], outline=(255, 150, 0), width=2)
        if fl & F_EXIT: d.ellipse([P(x - 1, z - 1), P(x + 1, z + 1)], fill=(255, 0, 255))
        if fl & F_FALL:
            u, v = P(x, z); d.line([u - 5, v - 5, u + 5, v + 5], fill=(255, 0, 0), width=2); d.line([u - 5, v + 5, u + 5, v - 5], fill=(255, 0, 0), width=2)
    n = {k: int(((tp['fl'] & f) > 0).sum()) for k, f in (('fall', F_FALL), ('exit', F_EXIT), ('pen', F_PEN), ('stuck', F_STUCK), ('rec', F_REC), ('rev', F_REV))}
    d.text((6, 6), f"run {tr['run']} pt {tr['pt']} {tr['mode']} seed {tr['seed']}  score {tr['score']:.0f}  " +
           ' '.join(f'{k} {v}' for k, v in n.items() if v) + f"  x {x0:.0f}..{x1:.0f} z {z0:.0f}..{z1:.0f}", fill=(255, 255, 255))
    img.save(path)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('level'); ap.add_argument('traces'); ap.add_argument('out')
    ap.add_argument('--px', type=float, default=4.0); ap.add_argument('--max', type=int, default=12)
    a = ap.parse_args()
    b, L = load(a.level); C = parse_col(b, L['col'])
    Path(a.out).mkdir(parents=True, exist_ok=True)
    trs = sorted(read_traces(a.traces), key=lambda t: -t['score'])[:a.max]
    for i, t in enumerate(trs):
        p = Path(a.out) / f"trace_{i:02d}_run{t['run']}_{t['mode']}.png"; render(C, t, p, a.px); print(p)

if __name__ == '__main__': main()
