"""Оценка нагрузки: сколько треугольников движок рисует в кадре в разных точках уровня.
Повторяет отсечение из viewer/main.c. python tools/budget.py [build/level.shr]"""
import sys, struct, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load(path):
    d = Path(path).read_bytes()
    assert d[:4] == b'SHR7'
    ntex, nch = struct.unpack_from('<II', d, 4)
    hd = struct.unpack_from('<11f3f', d, 12)
    W, H = struct.unpack_from('<II', d, 12 + 14 * 4)
    toff = struct.unpack_from('<I', d, 76)[0]
    hox, hoz, cell = hd[11], hd[12], hd[13]
    hm = np.frombuffer(d, '<i2', W * H * 4, 104).reshape(H, W, 4)   # заголовок SHR7 104 Б (@96 propOff, @100 carOff)
    recs = []
    for i in range(nch):
        r = struct.unpack_from('<6fiIIII3ffIII', d, toff + 80 * i)
        recs.append(dict(bb=r[:6], tex=r[6], flags=r[7], nv=r[8], ni=r[9], owner=r[10], off=r[15], nf=r[16], cell=r[17]))
    return dict(hd=hd, W=W, H=H, hm=hm, hox=hox, hoz=hoz, cell=cell, recs=recs, ntex=ntex, size=len(d))

def simulate(L, draw=115., lod=50., cone=(0.60, 0.80), step=6, cam_back=7.5, cam_up=3.2, extra=None):
    R = [r for r in L['recs'] if not r['owner']]
    bb = np.array([r['bb'] for r in R]); c = (bb[:, :3] + bb[:, 3:]) / 2
    rad = .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1)
    ni = np.array([r['ni'] for r in R]) // 3; nf = np.array([r['nf'] for r in R]) // 3
    nf = np.where(np.array([r['flags'] for r in R]) & 2048, ni, nf)   # флаг 2048 (правки 224/237/251): ближняя на любой дальности
    hm = L['hm']; res = []
    for gz in range(0, L['H'], step):
        for gx in range(0, L['W'], step):
            hs = hm[gz, gx]; hs = hs[hs != -32768]
            if not len(hs): continue
            y = hs.min() * .01; x = L['hox'] + (gx + .5) * L['cell']; z = L['hoz'] + (gz + .5) * L['cell']
            for h in np.arange(0, 2 * np.pi, np.pi / 4):
                e = np.array([x - np.sin(h) * cam_back, y + cam_up, z - np.cos(h) * cam_back])
                f = np.array([x, y + 1.4, z]) - e; f /= np.linalg.norm(f)
                dv = c - e; dist = np.linalg.norm(dv, axis=1)
                fw = dv @ f; side = np.sqrt(np.maximum(0, dist ** 2 - fw ** 2))
                vis = (dist - rad <= draw) & ~(side * cone[0] - fw * cone[1] > rad)
                far = dist - rad > lod
                t = np.where(far, nf, ni)[vis].sum()
                res.append((t, vis.sum(), x, z, h))
    return np.array(res)

if __name__ == '__main__' and '--sweep' not in sys.argv:
    L = load(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'build/level.shr')
    R = L['recs']
    print(f"файл {L['size']/2**20:.1f} MB, текстур {L['ntex']}, кусков {len(R)}, "
          f"треуг. всего {sum(r['ni'] for r in R if not r['owner'])//3:,}, машина {sum(r['ni'] for r in R if r['owner'])//3:,}")
    s = simulate(L)
    t = s[:, 0]
    print(f"точек {len(s)}: треуг./кадр  медиана {np.median(t)/1e3:.1f}k  p90 {np.percentile(t,90)/1e3:.1f}k  "
          f"p99 {np.percentile(t,99)/1e3:.1f}k  макс {t.max()/1e3:.1f}k;  кусков в кадре медиана {np.median(s[:,1]):.0f} макс {s[:,1].max():.0f}")
    i = t.argmax(); print(f"худшая точка x={s[i,2]:.0f} z={s[i,3]:.0f} h={s[i,4]:.2f}")

# ---------- дальность видимости: 60 FPS / 115 м против 30 FPS / дальше (docs/ДОП_АУДИТ_2026-09-27.md) ----------
# python tools/budget.py --sweep [level.shr]   -> таблица по дальностям: треуг./вызовы в кадре, мс на PSP по модели
# бенча v8, память клеток в радиусе загрузки, поток с карты памяти на скорости.
# Модель мс (аудит §4, bench_v8_psp.txt P2): кадр = ПОСТ + 0.66 мс/1k треуг. + 0.005 мс/вызов.
#   0.66 — ALLNEAR (+4.8k треуг. = +3.18 мс); 0.005 — остаток D100 после треугольников (-0.37 мс, -0.4k, -21 вызов);
#   ПОСТ = BASE 11.77 - 0.66*10.7 - 0.005*185 = 3.8 мс (заливка, небо, очистка, машина, HUD).
# Движок рисует меньше, чем эта модель (PVS до 115 м), поэтому треугольники калибруются на бенч:
#   движок(D) = бенч v8 (7.4k ср. / 12.5k макс при 115 м) + [модель(D) - модель(115)] (за 115 м PVS нет, всё честно).
MS_TRI, MS_DRAW = .66, .005
MS_CONST = 11.77 - MS_TRI * 10.7 - MS_DRAW * 185
BENCH_AVG_TRI, BENCH_MAX_TRI, BENCH_AVG_DRAW, BENCH_MAX_DRAW = 7.4, 12.5, 139, 244
LOOP = [(220, 172), (-300, 200), (-300, -250), (350, -150), (350, -550), (300, 500), (-50, 550), (220, 172)]

def cells(path):
    d = Path(path).read_bytes(); nc, co = struct.unpack_from('<II', d, 80)
    C = [struct.unpack_from('<6f6I', d, co + 48 * i) for i in range(nc)]
    C = [c for c in C if c[8] == 0]
    bb = np.array([c[:6] for c in C]); return (bb[:, :3] + bb[:, 3:]) / 2, .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1), np.array([c[10] for c in C])

def stream_need(path, load_r, speed=35., ahead=2.5):
    """Облёт кольца LOOP (как flypath) на speed м/с: сколько КБ/с надо читать, чтобы все клетки в радиусе
    load_r (+упреждение ahead с) были в памяти; и сколько МБ клеток в памяти (радиус выгрузки = load_r + 70)."""
    c, rad, size = cells(path); P = np.array(LOOP, float)
    seg = np.diff(P, axis=0); ln = np.linalg.norm(seg, axis=1); total = ln.sum()
    have = np.zeros(len(c), bool); per_s = []; ram = []; acc = 0.; t = 0.; dt = .25
    while t * speed < total:
        s = t * speed; i = np.searchsorted(np.cumsum(ln), s); i = min(i, len(ln) - 1)
        s0 = s - (np.cumsum(ln)[i] - ln[i]); dirv = seg[i] / ln[i]; p = P[i] + dirv * s0; q = p + dirv * speed * ahead
        dp = np.linalg.norm(c[:, [0, 2]] - p, axis=1) - rad; dq = np.linalg.norm(c[:, [0, 2]] - q, axis=1) - rad
        want = (dp < load_r) | (dq < load_r)
        new = want & ~have; acc += size[new].sum(); have |= want
        have &= ~((dp > load_r + 70) & (dq > load_r + 70))
        ram.append(size[have].sum())
        t += dt
        if abs(t - round(t)) < 1e-6: per_s.append(acc); acc = 0.
    per_s = np.array(per_s[3:]) / 1024   # первые секунды — стартовая загрузка круга
    return per_s.mean(), per_s.max(), max(ram) / 2**20

def sweep(L, path, dists=(115, 150, 200, 250, 300), step=12):
    base = None; rows = []
    for D in dists:
        s = simulate(L, draw=float(D), step=step)
        t, n = s[:, 0] / 1e3, s[:, 1]
        m = dict(D=D, avg=t.mean(), p99=np.percentile(t, 99), mx=t.max(), davg=n.mean(), dmx=n.max(), dp99=np.percentile(n, 99))
        if base is None: base = m
        et_avg = BENCH_AVG_TRI + m['avg'] - base['avg']; et_max = BENCH_MAX_TRI + m['p99'] - base['p99']
        m['dp99'] = np.percentile(n, 99)
        ed_avg = BENCH_AVG_DRAW + m['davg'] - base['davg']; ed_max = BENCH_MAX_DRAW + m['dp99'] - base['dp99']
        ms_avg = MS_CONST + MS_TRI * et_avg + MS_DRAW * ed_avg; ms_max = MS_CONST + MS_TRI * et_max + MS_DRAW * ed_max
        load_r = D + 75.; kbs, kbs_max, ram = stream_need(path, load_r)
        rows.append((D, et_avg, et_max, ed_avg, ed_max, ms_avg, ms_max, load_r, ram, kbs, kbs_max))
    print(' дальн | треуг. ср / худш | вызовы ср / худш | мс PSP ср / худш | загрузка, м | клетки в ОЗУ, МБ | поток 35 м/с, КБ/с ср / пик')
    for D, a, b, c_, d_, e, f, g, h, i, j in rows:
        print(f' {D:4d} м | {a:5.1f}k / {b:5.1f}k | {c_:5.0f} / {d_:5.0f} | {e:5.1f} / {f:5.1f} | {g:5.0f} | {h:5.2f} | {i:5.0f} / {j:5.0f}')
    return rows

if __name__ == '__main__' and '--sweep' in sys.argv:
    a = [x for x in sys.argv[1:] if x != '--sweep']; path = a[0] if a else ROOT / 'build/level.shr'
    sweep(load(path), path)
