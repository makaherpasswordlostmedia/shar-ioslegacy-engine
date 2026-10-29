"""Правка 508: оценка выигрыша «дальней версии куска без нарезки» (исходные треугольники города, рёбра > FAR_SPLIT 28 м режутся пополам, а не
рёбра > 14 м/7 м у ближней). Данные: tools/psp_export.py с SHR_FAR_PLAIN=1 пишет дальнюю версию в файл (nf > 0; движок её не рисует, флаг 2048),
tools/pvs --range 250 считает списки. Модель кадра — tools/pvs_frame_est.py: 180 клеток PVS × 4 курса, камера как в budget.py, режим 250 м.
python tools/far_plain_est.py LEVEL_with_far_and_pvs.shr [D1,D2,...]   (дальше D м от глаза по ящику куска — дальняя версия)"""
import sys, struct, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import budget as B
path = sys.argv[1]; Ds = [float(x) for x in (sys.argv[2] if len(sys.argv) > 2 else '50,60,80,100').split(',')]
draw = 250.
L = B.load(path); recs = L['recs']
own = np.array([r['owner'] for r in recs]); bb = np.array([r['bb'] for r in recs]); lo, hi = bb[:, :3], bb[:, 3:]
c = (lo + hi) / 2; rad = .5 * np.linalg.norm(hi - lo, axis=1)
ni = np.array([r['ni'] for r in recs]) // 3; nf = np.array([r['nf'] for r in recs]) // 3; fl = np.array([r['flags'] for r in recs])
cellid = np.array([r['cell'] for r in recs]); opaque = (fl & 2) == 0
has_far = nf > 0
print(f'кусков города {int((own == 0).sum())}, треуг. ближних {ni[own == 0].sum():,}, дальних (исходные) {nf[own == 0].sum():,} ({100 * nf[own == 0].sum() / max(ni[own == 0].sum(), 1):.0f} %)')
d = open(path, 'rb').read(); off = struct.unpack_from('<I', d, 88)[0]
ox, oz, cell = struct.unpack_from('<3f', d, off + 4); W, H, pool, pad = struct.unpack_from('<4I', d, off + 16)
ent = np.frombuffer(d, '<u4', 2 * W * H, off + 32).reshape(-1, 2); pl = np.frombuffer(d, '<u2', pool, off + 32 + 8 * W * H)
def lst(x, z):
    gx = int((x - ox) // cell); gz = int((z - oz) // cell)
    if not (0 <= gx < W and 0 <= gz < H): return None
    s, n = ent[gz * W + gx]; return None if n == 0xFFFFFFFF else pl[s:s + n]
cone = (0.60, 0.80); hm = L['hm']; rows = []
cell_near = np.bincount(cellid[(own == 0) & opaque], weights=ni[(own == 0) & opaque], minlength=int(cellid[own == 0].max()) + 1)
cell_far = np.bincount(cellid[(own == 0) & opaque], weights=np.where(has_far, nf, ni)[(own == 0) & opaque], minlength=len(cell_near))
for gz in range(0, H, 2):
    for gx in range(0, W, 2):
        x = ox + (gx + .5) * cell; z = oz + (gz + .5) * cell; l = lst(x, z)
        if l is None: continue
        hx = int((x - L['hox']) // L['cell']); hz = int((z - L['hoz']) // L['cell'])
        if not (0 <= hx < L['W'] and 0 <= hz < L['H']): continue
        hs = hm[hz, hx]; hs = hs[hs != -32768]
        if not len(hs): continue
        y = hs.min() * .01
        mask = np.zeros(len(recs), bool); mask[l] = True
        for h in np.arange(0, 2 * np.pi, np.pi / 2):
            e = np.array([x - np.sin(h) * 7.5, y + 3.2, z - np.cos(h) * 7.5]); f = np.array([x, y + 1.4, z]) - e; f /= np.linalg.norm(f)
            dv = c - e; dist = np.linalg.norm(dv, axis=1); fw = dv @ f; side = np.sqrt(np.maximum(0, dist ** 2 - fw ** 2))
            vis = mask & (dist - rad <= draw) & ~(side * cone[0] - fw * cone[1] > rad) & (own == 0)
            bd = np.linalg.norm(np.maximum(np.maximum(lo - e, e - hi), 0), axis=1)   # расстояние до ящика (метрика движка)
            row = [ni[vis].sum()]
            for D in Ds:
                far = vis & has_far & (bd > D); row.append(np.where(far, nf, ni)[vis].sum())
            # модель листов клеток: клетка целиком; дальняя версия клетки — если все её видимые куски дальше D
            cells = np.unique(cellid[vis & opaque])
            cn = cell_near[cells].sum() + ni[vis & ~opaque].sum(); row.append(cn)
            for D in Ds:
                cbd = np.array([bd[(cellid == ci) & vis].min() for ci in cells]) if len(cells) else np.zeros(0)
                row.append(np.where(cbd > D, cell_far[cells], cell_near[cells]).sum() + ni[vis & ~opaque].sum())
            rows.append(row)
r = np.array(rows, float); k = len(Ds)
print(f'кадров {len(r)}; треугольников в кадре (PVS 250 м + пирамида):')
print(f'  по кускам  сейчас p50 {np.median(r[:, 0]) / 1e3:5.1f}k ср. {r[:, 0].mean() / 1e3:5.1f}k p90 {np.percentile(r[:, 0], 90) / 1e3:5.1f}k')
for i, D in enumerate(Ds): print(f'  по кускам  дальняя версия дальше {D:3.0f} м: p50 {np.median(r[:, 1 + i]) / 1e3:5.1f}k ср. {r[:, 1 + i].mean() / 1e3:5.1f}k p90 {np.percentile(r[:, 1 + i], 90) / 1e3:5.1f}k  ({100 * (1 - r[:, 1 + i].mean() / r[:, 0].mean()):.0f} % меньше)')
print(f'  по листам клеток сейчас p50 {np.median(r[:, 1 + k]) / 1e3:5.1f}k ср. {r[:, 1 + k].mean() / 1e3:5.1f}k p90 {np.percentile(r[:, 1 + k], 90) / 1e3:5.1f}k')
for i, D in enumerate(Ds): print(f'  по листам клеток дальше {D:3.0f} м: p50 {np.median(r[:, 2 + k + i]) / 1e3:5.1f}k ср. {r[:, 2 + k + i].mean() / 1e3:5.1f}k p90 {np.percentile(r[:, 2 + k + i], 90) / 1e3:5.1f}k  ({100 * (1 - r[:, 2 + k + i].mean() / r[:, 1 + k].mean()):.0f} % меньше)')
