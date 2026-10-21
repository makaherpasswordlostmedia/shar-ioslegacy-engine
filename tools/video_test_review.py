#!/usr/bin/env python3
"""Разбор видео TEST17 (iPhone, 60 к/с, экран PSP в кадре): ffmpeg + numpy, CPU, без AI.

  tools/video_test_review.py VIDEO --smoke build/smoke/<время>/smoke.txt [--out DIR] [--corners x0,y0,x1,y1,x2,y2,x3,y3]
  tools/video_test_review.py --selftest            синтетика: экран с перекосом, вспышки сцен, мигание, pop-in; плюс красный контроль

Этапы:
 1. экран PSP: берём несколько кадров, среднюю яркость, порог Отсу, крупнейшее прямоугольное пятно, 4 угла (TL TR BL BR);
    --corners — руками в пикселях кадра; --detect-only — только preview_corners.png. Выпрямление — фильтр ffmpeg perspective -> 480x272.
 2. сцены: белая квадратная вспышка в углу (--flash-box x0,y0,x1,y1 на 480x272 (по умолчанию метка TEST17 436,4,476,44)) на 1 кадр в начале сцены;
    n-я вспышка = n-я строка SCENE в smoke.txt (начало сцены t, с). --skip-scenes N — если сцен в видео меньше/больше.
 3. мигание: блок 24x24 px (на 480x272) резко меняет цвет (> --thr) и через 1-3 кадра возвращается; pop-in: блок скачком меняется
    и остаётся, при спокойном остальном кадре. Оверлей (--mask-overlay x0,y0,x1,y1 доли кадра, по умолчанию верхний левый угол) и угол вспышки
    маскируются; глобальные скачки (> --max-frac блоков) — тряска/экспозиция, не считаются.
 4. отчёт OUT/report.md + report.json + events/NNN.png: сцена · время теста · кадр видео · полоса 3 кадра до/после с рамкой.
Известные пределы: углы экрана считаются один раз (рука с телефоном дрожит — сдвиг даёт ложные края, поэтому снимать с упора);
если экран плохо отличается от рамки — задать --corners. Время теста = t начала сцены + (кадр - кадр вспышки)/fps видео.
"""
import argparse, json, os, re, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

PROFILES = {   # flash — метка сцены на 480x272, mask — подложка оверлея долями кадра
    'test18': {'flash': [0, 260, 12, 272], 'mask': [0, .94, .85, 1.]},
    'test17': {'flash': [436, 4, 476, 44], 'mask': [0, 0, .85, .21]},
}


def apply_profile(a):
    pr = PROFILES[a.profile]
    if a.flash_box is None: a.flash_box = pr['flash']
    if getattr(a, 'mask_overlay', 1) is None: a.mask_overlay = pr['mask']
    return a


OW, OH = 480, 272            # выпрямленный экран PSP
SW, SH = 120, 68             # уменьшенный кадр для анализа (блок 6x6 = 24x24 px экрана)
BLK = 6


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    j = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-of', 'json', path], capture_output=True).stdout)['streams'][0]
    w, h = int(j['width']), int(j['height'])
    rot = 0
    for sd in j.get('side_data_list', []):
        if 'rotation' in sd: rot = int(sd['rotation'])
    if abs(rot) == 90: w, h = h, w
    n, d = (j.get('avg_frame_rate') or j['r_frame_rate']).split('/')
    return dict(w=w, h=h, fps=float(n) / float(d), dur=float(j.get('duration') or 0), nb=int(j.get('nb_frames') or 0))


def grab(path, t, width):
    info = probe(path); h = int(round(info['h'] * width / info['w'] / 2)) * 2
    b = run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-vf', f'scale={width}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
            capture_output=True).stdout
    if len(b) < width * h * 3: return None
    return np.frombuffer(b, np.uint8).reshape(h, width, 3)


# ---------------------------------------------------------------- 1. экран
def otsu(v):
    hist, _ = np.histogram(v, 256, (0, 256)); p = hist / hist.sum(); w = np.cumsum(p); mu = np.cumsum(p * np.arange(256)); mt = mu[-1]
    with np.errstate(divide='ignore', invalid='ignore'): s = (mt * w - mu) ** 2 / (w * (1 - w))
    return int(np.nanargmax(s))


def components(mask):
    """4-связные пятна: список массивов (y, x); маска небольшая (≈ 240x135)"""
    H, W = mask.shape; seen = np.zeros_like(mask, bool); out = []
    for y0 in range(H):
        for x0 in range(W):
            if mask[y0, x0] and not seen[y0, x0]:
                st = [(y0, x0)]; seen[y0, x0] = True; pts = []
                while st:
                    y, x = st.pop(); pts.append((y, x))
                    for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]: seen[yy, xx] = True; st.append((yy, xx))
                out.append(np.array(pts))
    return out


def _edge_run(D, lim):
    """1-D маска тёмного D: от индекса 0 до lim — первая тёмная полоса >= 3 px (рамка экрана); -> индекс первого светлого пикселя после неё или None"""
    i = 0
    while i < lim:
        if D[i:i + 3].all():
            j = i
            while j < lim and D[j]: j += 1
            return j if j < lim else None
        i += 1
    return None


def _fit(pts):
    """[(t, v)] -> (a, b) v = a t + b, с отбросом выбросов; None если мало точек"""
    if len(pts) < 4: return None
    t = np.array([p[0] for p in pts], float); v = np.array([p[1] for p in pts], float)
    a, b = np.polyfit(t, v, 1)
    for _ in range(2):
        r = np.abs(v - (a * t + b)); keep = r <= max(2.0, 2 * np.median(r))
        if keep.sum() < 4: return None
        a, b = np.polyfit(t[keep], v[keep], 1)
    return a, b


def find_screen_bezel(frames):
    """экран в тёмной рамке PSP: по яркости (максимум во времени) идём к центру от краёв кадра и ищем внутреннюю границу рамки; 4 прямые -> 4 угла (TL TR BL BR)"""
    L = np.max([f.astype(np.float32) @ [.299, .587, .114] for f in frames], 0); H, W = L.shape
    D = L < .35 * np.percentile(L, 85)
    xl, xr, yt, yb = [], [], [], []
    for y in np.linspace(.25 * H, .75 * H, 17).astype(int):
        a = _edge_run(D[y], int(.35 * W)); b = _edge_run(D[y][::-1], int(.35 * W))
        if a is not None: xl.append((y, a))
        if b is not None: xr.append((y, W - 1 - b))
    lx = np.mean([p[1] for p in xl]) if xl else .1 * W; rx = np.mean([p[1] for p in xr]) if xr else .9 * W
    for x in np.linspace(lx + .30 * (rx - lx), lx + .70 * (rx - lx), 17).astype(int):   # низ — по середине экрана
        b = _edge_run(D[:, x][::-1], int(.35 * H))
        if b is not None: yb.append((x, H - 1 - b))
    for x in np.linspace(lx + .88 * (rx - lx), lx + .97 * (rx - lx), 9).astype(int):   # верх — правее подложки оверлея TEST17 (она до ~85 % ширины и сливается с рамкой)
        a = _edge_run(D[:, x], int(.35 * H))
        if a is not None: yt.append((x, a))
    ls = [_fit(p) for p in (xl, xr, yt, yb)]
    if any(l is None for l in ls): return None
    (la, lb), (ra, rb), (ta, tb), (ba, bb) = ls          # x = la*y+lb ; x = ra*y+rb ; y = ta*x+tb ; y = ba*x+bb
    def cross(a1, b1, a2, b2):   # x = a1*y+b1, y = a2*x+b2
        y = (a2 * b1 + b2) / (1 - a1 * a2); return (a1 * y + b1, y)
    q = np.array([cross(la, lb, ta, tb), cross(ra, rb, ta, tb), cross(la, lb, ba, bb), cross(ra, rb, ba, bb)], float)
    w = np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[3] - q[2]); h = np.linalg.norm(q[2] - q[0]) + np.linalg.norm(q[3] - q[1]); asp = w / max(h, 1e-6)
    cr = lambda u, v: u[0] * v[1] - u[1] * v[0]; area = .5 * abs(cr(q[1] - q[0], q[2] - q[0])) + .5 * abs(cr(q[1] - q[3], q[2] - q[3]))
    if not (1.4 < asp < 2.2 and .12 < area / (W * H) < .99): return None
    im = Image.fromarray(frames[0]); d = ImageDraw.Draw(im); d.polygon([tuple(q[i]) for i in (0, 1, 3, 2)], outline=(255, 0, 0))
    return q, np.asarray(im), .9


def find_screen(frames):
    """-> (углы TL,TR,BL,BR в пикселях кадра frames[0], preview RGB, оценка 0..1) или None"""
    G = np.mean([f.astype(np.float32) @ [.299, .587, .114] for f in frames], 0)
    H, W = G.shape; k = max(1, W // 240); sm = G[:H // k * k, :W // k * k].reshape(H // k, k, W // k, k).mean((1, 3))
    th = otsu(sm.clip(0, 255)); best = None
    for mask in (sm > th,):   # экран светлее рамки; тёмный экран — задать --corners
        for pts in components(mask):
            a = len(pts) / mask.size
            if not .04 < a < .85: continue
            y, x = pts[:, 0].astype(float), pts[:, 1].astype(float)
            c = [pts[np.argmin(x + y)], pts[np.argmax(x - y)], pts[np.argmin(x - y)], pts[np.argmax(x + y)]]   # TL TR BL BR
            q = np.array([[p[1], p[0]] for p in c], float)
            cr = lambda u, v: u[0] * v[1] - u[1] * v[0]
            area = .5 * abs(cr(q[1] - q[0], q[2] - q[0])) + .5 * abs(cr(q[1] - q[3], q[2] - q[3]))
            fill = min(1.0, len(pts) / max(area, 1)); wd = np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[3] - q[2]); ht = np.linalg.norm(q[2] - q[0]) + np.linalg.norm(q[3] - q[1])
            asp = wd / max(ht, 1e-6); ar = min(asp, 16 / 9) / max(asp, 16 / 9)
            score = fill * ar * min(1.0, a / .15)
            if best is None or score > best[0]: best = (score, q * k + k / 2)
    if best is None: return None
    q = best[1]; im = Image.fromarray(frames[0]); d = ImageDraw.Draw(im)
    d.polygon([tuple(q[i]) for i in (0, 1, 3, 2)], outline=(255, 0, 0)); [d.ellipse([q[i][0] - 8, q[i][1] - 8, q[i][0] + 8, q[i][1] + 8], outline=(255, 255, 0), width=3) for i in range(4)]
    return q, np.asarray(im), best[0]


def decode_rect(path, q, info, w2=1920, start=None, dur=None):
    """генератор выпрямленных кадров 480x272 RGB"""
    # perspective: углы источника -> углы кадра (TL TR BL BR); потом кадр целиком уменьшается до 480x272 (при другом соотношении сторон кадра экран тянется — это нормально)
    s = w2 / info['w']; h2 = int(round(info['h'] * s / 2)) * 2; qq = q * s
    pf = 'perspective=' + ':'.join(f'x{i}={qq[i][0]:.2f}:y{i}={qq[i][1]:.2f}' for i in range(4)) + ':interpolation=linear:sense=source'
    ss = ['-ss', f'{start:.3f}'] if start else []; tt = ['-t', f'{dur:.3f}'] if dur else []
    p = subprocess.Popen(['ffmpeg', '-v', 'error'] + ss + ['-i', path] + tt + ['-vf', f'scale={w2}:{h2},{pf},scale={OW}:{OH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    n = OW * OH * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            yield np.frombuffer(b, np.uint8).reshape(OH, OW, 3)
    finally:
        p.stdout.close(); p.wait()


# ---------------------------------------------------------------- 2. сцены
def corner_box(corner, size):
    x = 0 if corner[1] == 'l' else OW - size; y = 0 if corner[0] == 't' else OH - size
    return x, y, x + size, y + size


def find_flashes(lum, fps, min_gap_s=.5, hi=190., rise=70.):
    """lum — яркость угла по кадрам. -> индексы кадров вспышек (первый кадр вспышки)"""
    n = len(lum); out = []
    for i in range(n):
        if lum[i] < hi: continue
        a = np.median(lum[max(0, i - 8):i]) if i else lum[i] - 999; b = np.median(lum[i + 3:i + 11]) if i + 3 < n else a
        base = min(a, b)
        if lum[i] - base < rise: continue
        if i and lum[i - 1] >= hi and lum[i - 1] - base >= rise: continue    # вспышка на 2 кадра — берём первый
        L = 0
        while i + L < n and lum[i + L] >= hi - 25: L += 1
        if not 3 <= L <= 10: continue                                      # метка TEST17 — 3 игровых кадра = 5-6 видеокадров; долгий белый фон — не метка
        if out and i - out[-1] < min_gap_s * fps: continue
        out.append(i)
    return out


def parse_smoke(path):
    """-> (сцены [(имя, t)] по строкам SCENE, метки [(имя, t первого кадра)] по строкам OVFLASH f=1; одна метка на сцену)"""
    sc = []; ov = []; seen = set()
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'SCENE\s+(\S+)\s+([\d.]+)', ln)
        if m: sc.append((m.group(1), float(m.group(2)))); continue
        m = re.match(r'OVFLASH scene=(\S+) f=(\d+) t=([\d.]+) left=(\d+)', ln)
        if m and int(m.group(4)) == 3: ov.append((m.group(1), float(m.group(3))))   # первый кадр метки (left 3 -> 1); f в логе — сквозной номер кадра игры
    return sc, ov


def match_flashes(flashes, fps, ov, slack=-1.5, maxload=60.0, maxskip=4, maxoff=600.0):
    """кадры вспышек видео -> строки OVFLASH лога. Часы видео и теста НЕ параллельны: загрузка уровней идёт в реальном времени дольше, чем t теста
    (t считает кадры игры), поэтому по времени сопоставлять нельзя. Ищем самую длинную монотонную цепочку пар, где разрыв между метками в видео не меньше
    разрыва t в логе (с допуском slack) и не больше него плюс maxload с; лишние вспышки видео (ложные) и пропущенные (до maxskip подряд) допускаются.
    -> ([(кадр, имя, t)], число вспышек видео без пары)"""
    if not flashes or not ov: return [], len(flashes)
    N, M = len(flashes), len(ov); vt = [f / fps for f in flashes]; INF = -10 ** 9
    best = [[(INF, 0.0, None)] * N for _ in range(M)]            # (число пар, сумма |лишнее|, предыдущее (j, i))
    for j in range(M):
        for i in range(N):
            off_ = vt[i] - ov[j][1]
            if off_ < -0.5 or off_ > maxoff: continue   # видео не может опережать тест (запись начата не позже старта) и не отстаёт на сотни секунд
            cand = (1, 0.0, None)
            for jp in range(max(0, j - maxskip - 1), j):
                dt = ov[j][1] - ov[jp][1]
                for ip in range(i):
                    b = best[jp][ip]
                    if b[0] < 1: continue
                    dv = vt[i] - vt[ip]; ex = dv - dt
                    if ex < slack or ex > maxload: continue
                    c = (b[0] + 1, b[1] + abs(ex) * .01, (jp, ip))
                    if c[0] > cand[0] or (c[0] == cand[0] and c[1] < cand[1]): cand = c
            best[j][i] = cand
    end = max(((best[j][i][0], -best[j][i][1], j, i) for j in range(M) for i in range(N)))
    chain = []; cur = (end[2], end[3])
    while cur is not None: chain.append(cur); cur = best[cur[0]][cur[1]][2]
    chain.reverse(); out = [(flashes[i], ov[j][0], ov[j][1]) for j, i in chain]
    return out, N - len(out)


# ---------------------------------------------------------------- 3. детекторы
def blocks_of(small):
    """small (n,SH,SW,3) -> (n, SH//BLK, SW//BLK, 3) средний цвет блока"""
    n = small.shape[0]; h, w = SH // BLK * BLK, SW // BLK * BLK
    return small[:, :h, :w].reshape(n, h // BLK, BLK, w // BLK, BLK, 3).astype(np.float32).mean((2, 4))


def mask_blocks(gh, gw, boxes):
    m = np.zeros((gh, gw), bool)
    for x0, y0, x1, y1 in boxes:   # в долях экрана
        m[int(y0 * gh):int(np.ceil(y1 * gh)), int(x0 * gw):int(np.ceil(x1 * gw))] = True
    return m


def clusters(flag):
    H, W = flag.shape; seen = np.zeros_like(flag); out = []
    for y0 in range(H):
        for x0 in range(W):
            if flag[y0, x0] and not seen[y0, x0]:
                st = [(y0, x0)]; seen[y0, x0] = True; pts = []
                while st:
                    y, x = st.pop(); pts.append((y, x))
                    for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1), (y + 1, x + 1), (y - 1, x - 1), (y + 1, x - 1), (y - 1, x + 1)):
                        if 0 <= yy < H and 0 <= xx < W and flag[yy, xx] and not seen[yy, xx]: seen[yy, xx] = True; st.append((yy, xx))
                out.append(pts)
    return out


def detect(B, masked, thr, max_frac, quiet_frames, flash_frames, fps):
    B = B.astype(np.float32); n, gh, gw, _ = B.shape; ev = []
    d = np.abs(B[1:] - B[:-1]).max(3)                 # d[i-1] = скачок кадра i относительно i-1
    skip = np.zeros(n, bool)
    for f in flash_frames: skip[max(0, f - 2):f + quiet_frames + 1] = True
    for i in range(1, n - 5):
        if skip[i]: continue
        jump = (d[i - 1] > thr) & ~masked
        k = int(jump.sum())
        if k == 0 or k > max_frac * gh * gw: continue
        calm = d[i - 1][~jump & ~masked].mean() if (~jump & ~masked).any() else 0
        ref = B[i - 1]
        ret = np.zeros((gh, gw), bool); stay = np.zeros((gh, gw), bool)
        for kk in (1, 2, 3):
            back = np.abs(B[i + kk] - ref).max(2) < thr / 3
            ret |= back
        after = B[i + 3]
        stay = (np.abs(after - ref).max(2) > thr * .6) & (np.abs(after - B[i + 1]).max(2) < thr / 3) & (np.abs(ref - B[max(0, i - 3)]).max(2) < thr / 3)   # до скачка блок стоял спокойно
        if calm > thr / 5: continue   # остальной кадр живой (камера едет, сдвиг всей картинки) — это не локальное изменение
        for kind, sel in (('мигание', jump & ret), ('pop-in', jump & stay)):
            if not sel.any(): continue
            for pts in clusters(sel):
                ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                if kind == 'pop-in':   # появилось или пропало: область после скачка ближе к окружению, чем до него — объект пропал/слился с фоном
                    y0_, y1_, x0_, x1_ = min(ys), max(ys) + 1, min(xs), max(xs) + 1
                    ring = B[:, max(0, y0_ - 1):y1_ + 1, max(0, x0_ - 1):x1_ + 1].reshape(n, -1, 3)
                    reg = B[:, y0_:y1_, x0_:x1_].mean((1, 2)); rr = (ring.sum(1) - B[:, y0_:y1_, x0_:x1_].reshape(n, -1, 3).sum(1)) / max(1, ring.shape[1] - (y1_ - y0_) * (x1_ - x0_))
                    k_ = min(n - 1, i + 3)
                    if np.abs(reg[k_] - rr[k_]).max() < np.abs(reg[i - 1] - rr[i - 1]).max(): kind = 'pop-out'
                ev.append(dict(kind=kind, frame=i, blocks=len(pts), box=[min(xs) * BLK * OW // (gw * BLK), min(ys) * BLK * OH // (gh * BLK),
                               (max(xs) + 1) * OW // gw, (max(ys) + 1) * OH // gh], jump=float(max(d[i - 1][y, x] for y, x in pts))))
    # одно событие на область и вид, если они идут подряд кадров <= 2
    ev.sort(key=lambda e: (e['kind'], e['frame'])); out = []
    for e in ev:
        if out and out[-1]['kind'] == e['kind'] and e['frame'] - out[-1]['frame'] <= 2 and abs(e['box'][0] - out[-1]['box'][0]) < 48 and abs(e['box'][1] - out[-1]['box'][1]) < 48: continue
        out.append(e)
    out.sort(key=lambda e: e['frame']); res = []   # серия из одной причины (соседние кадры, та же область) — одно событие, берём сильнейшее
    for e in out:
        for r_ in res[-6:]:
            if e['frame'] - r_['frame'] <= 12 and abs(e['box'][0] - r_['box'][0]) < 72 and abs(e['box'][1] - r_['box'][1]) < 72:
                if e['jump'] * e['blocks'] ** .5 > r_['jump'] * r_['blocks'] ** .5: r_.update(e)
                break
        else: res.append(e)
    return res


# ---------------------------------------------------------------- 4. отчёт
def font_text(im, xy, s, fill=(255, 255, 0)):
    d = ImageDraw.Draw(im); d.text((xy[0] + 1, xy[1] + 1), s, fill=(0, 0, 0)); d.text(xy, s, fill=fill)


def strip(frames_by_idx, e, scale=2):
    i = e['frame']; x0, y0, x1, y1 = e['box']; m = 24
    x0, y0, x1, y1 = max(0, x0 - m), max(0, y0 - m), min(OW, x1 + m), min(OH, y1 + m)
    if x1 - x0 < 96: c = (x0 + x1) // 2; x0, x1 = max(0, c - 48), min(OW, c + 48)
    if y1 - y0 < 72: c = (y0 + y1) // 2; y0, y1 = max(0, c - 36), min(OH, c + 36)
    cw, ch = (x1 - x0) * scale, (y1 - y0) * scale; offs = list(range(-3, 4)); sheet = Image.new('RGB', (cw * len(offs), ch + 14), (30, 30, 30))
    for k, o in enumerate(offs):
        f = frames_by_idx.get(i + o)
        if f is None: continue
        cr = Image.fromarray(f).crop((x0, y0, x1, y1)).resize((cw, ch), Image.NEAREST); sheet.paste(cr, (k * cw, 14))
        font_text(sheet, (k * cw + 2, 1), f'{o:+d}', (255, 255, 255) if o else (255, 200, 0))
        if True:
            d = ImageDraw.Draw(sheet); bx = [(e['box'][0] - x0) * scale + k * cw, (e['box'][1] - y0) * scale + 14, (e['box'][2] - x0) * scale + k * cw, (e['box'][3] - y0) * scale + 14]
            d.rectangle(bx, outline=(255, 0, 0) if o == 0 else (120, 60, 60))
    return sheet


def parse_out_of_game(smoke):
    """интервалы t теста вне игры: экраны загрузки/карточки/ирис (строки лога st=load|brief|iris, шаг <=1.5 с) и целиком сцены *_load. -> [(t0, t1)]"""
    ts = []; scenes = []
    for ln in open(smoke, encoding='utf-8', errors='replace'):
        m = re.match(r'(\d+\.\d+) \S+ .*st=(load|brief|iris)', ln)
        if m: ts.append(float(m.group(1))); continue
        m = re.match(r'SCENE\s+(\S+)\s+([\d.]+)', ln)
        if m: scenes.append((m.group(1), float(m.group(2))))
    iv = []
    for t in sorted(ts):
        if iv and t - iv[-1][1] <= 1.5: iv[-1][1] = t + .7
        else: iv.append([t - .7, t + .7])
    for k, (n, t) in enumerate(scenes):
        if '_load' in n: iv.append([t, scenes[k + 1][1] if k + 1 < len(scenes) else t + 60])
    return [tuple(x) for x in iv]


def make_time_to_t(a, matched, fps):
    """функция видео-секунды -> t теста: точная карта --timemap (пары [видео с, t]), иначе по метками из ИНДЕКСа"""
    if a.timemap:
        pts = json.load(open(a.timemap)); v = np.array([p[0] for p in pts], float); t = np.array([p[1] for p in pts], float)
    elif matched:
        v = np.array([m[0] / fps for m in matched], float); t = np.array([m[2] for m in matched], float)
    else: return None
    def f(vs):
        if vs < v[0]: return float(t[0] - (v[0] - vs))
        if vs > v[-1]: return float(t[-1] + (vs - v[-1]))
        return float(np.interp(vs, v, t))
    f.v0, f.v1 = float(v[0]), float(v[-1]); return f


def in_game_filter(ev, fps, n, to_t, oog, edge=30.0, tmax=None):
    """оставляет события игровых отрезков: не первые/последние edge с записи, не до старта теста/после конца карты, не экраны загрузки/карточки"""
    keep = []
    for e in ev:
        vs = e['frame'] / fps
        if vs < edge or vs > n / fps - edge: continue
        if to_t:
            t = to_t(vs)
            if t < 0 or (tmax and t > tmax) or vs < to_t.v0 - 15 or vs > to_t.v1 + 15: continue
            if any(a <= t <= b for a, b in oog): continue
        keep.append(e)
    return keep


def scene_of(frame, flashes, scenes, skip, matched=None):
    k = -1
    if matched:
        for j, (f, n, t) in enumerate(matched):
            if f <= frame: k = j
        return (matched[k][1], matched[k][2], matched[k][0]) if k >= 0 else (None, None, None)
    for j, f in enumerate(flashes):
        if f <= frame: k = j
    idx = k + skip
    if k < 0 or idx >= len(scenes): return None, None, None
    return scenes[idx][0], scenes[idx][1], flashes[k]


def review(a):
    info = probe(a.video); fps = info['fps']; print(f'видео {info["w"]}x{info["h"]} {fps:.2f} к/с {info["dur"]:.1f} с', flush=True)
    os.makedirs(a.out, exist_ok=True)
    if a.corners: q = np.array(a.corners, float).reshape(4, 2); score = 1.0
    else:
        ts = np.linspace(.1, max(.2, info['dur'] - .2), 24); fr = [g for g in (grab(a.video, t, 960) for t in ts) if g is not None]
        r0 = find_screen_bezel(fr)    # штатив: максимум яркости по всем кадрам убирает тёмные куски игры, остаётся одна рамка
        rs = [r_ for r_ in (find_screen_bezel([g]) for g in fr) if r_] if not r0 else []    # рамка — по каждому кадру отдельно (рука двигает телефон), углы — медиана
        r = r0 or ((np.median([r_[0] for r_ in rs], 0), rs[0][1], .9) if len(rs) >= max(3, len(fr) // 3) else (find_screen(fr) if fr else None))
        if not r: print('экран не найден: задай --corners'); return 2
        q, prev, score = r; Image.fromarray(prev).save(os.path.join(a.out, 'preview_corners.png')); q = q * (info['w'] / 960)
        print(f'углы экрана (оценка {score:.2f}):', ' '.join(f'({x:.0f},{y:.0f})' for x, y in q), flush=True)
        if a.detect_only: return 0
    fx0, fy0, fx1, fy1 = [int(v) for v in a.flash_box]; m_ = (fx1 - fx0) // 4; cx0, cy0, cx1, cy1 = fx0 + m_, fy0 + m_, fx1 - m_, fy1 - m_   # яркость — по середине метки: углы выпрямленного кадра чуть смещены
    small = []; lum = []; SEG = 300.0; nseg = int(np.ceil(info['dur'] / SEG)) if info['dur'] else 1
    for k in range(nseg):   # кусками по 300 с: кэш каждого куска, при сбое продолжается с недостающего
        t0 = k * SEG; nominal = int(round(min(SEG, info['dur'] - t0) * fps)) if info['dur'] else 0
        fn = f'{a.cache}.seg{k:03d}.npy' if a.cache else None
        if fn and os.path.exists(fn) and os.path.exists(fn + '.lum.npy'):
            sb = np.load(fn); sl = np.load(fn + '.lum.npy')
        else:
            sb = []; sl = []
            for f in decode_rect(a.video, q, info, start=t0, dur=SEG):
                sl.append(float((f[cy0:cy1, cx0:cx1].astype(np.float32) @ np.array([.299, .587, .114], np.float32)).mean()))
                sb.append(f[:264].reshape(11, 24, 20, 24, 3).mean((1, 3)).astype(np.float16))   # блоки 24x24 px экрана: средний цвет
            sb = np.array(sb); sl = np.array(sl)
            if nominal and len(sb) < nominal * .98: print(f'ВНИМАНИЕ: кусок {k} ({t0:.0f} с): {len(sb)} кадров из {nominal}', flush=True)
            if nominal and len(sb):   # ровно nominal кадров, чтобы номера кадров не плыли
                if len(sb) > nominal: sb, sl = sb[:nominal], sl[:nominal]
                elif len(sb) < nominal: sb = np.concatenate([sb, np.repeat(sb[-1:], nominal - len(sb), 0)]); sl = np.concatenate([sl, np.repeat(sl[-1:], nominal - len(sl))])
            if fn and len(sb): np.save(fn, sb); np.save(fn + '.lum.npy', sl)
            print(f'кусок {k + 1}/{nseg} готов', flush=True)
        small.append(sb); lum.append(sl)
    small = np.concatenate(small); lum = np.concatenate(lum)
    n = len(small); print(f'кадров {n}', flush=True)
    flashes = find_flashes(lum, fps); scenes, ov = parse_smoke(a.smoke) if a.smoke else ([], [])
    matched, lost = match_flashes(flashes, fps, ov) if ov else ([], 0)
    if a.index:   # ИНДЕКС.tsv от video_split_scenes.py: начала сцен по кадрам видео (метка или оценка); этим же временем считается t теста
        matched = []
        for ln in list(open(a.index, encoding='utf-8'))[1:]:
            c = ln.rstrip('\n').split('\t'); matched.append((max(0, int(float(c[2]) * fps)), c[1], float(c[4])))
    if ov: print(f'OVFLASH в логе: {len(ov)} сцен, вспышек в видео {len(flashes)}, сопоставлено {len(matched)}, без пары {lost}', flush=True)
    sk = a.skip_scenes
    print(f'вспышек {len(flashes)}, сцен в smoke.txt {len(scenes)}', flush=True)
    gh, gw = SH // BLK, SW // BLK
    boxes = [tuple(a.mask_overlay)] + [(fx0 / OW, fy0 / OH, fx1 / OW, fy1 / OH)]
    masked = mask_blocks(gh, gw, boxes)
    ev = detect(small, masked, a.thr, a.max_frac, a.quiet, [m[0] for m in matched] if a.index else flashes, fps)
    to_t = make_time_to_t(a, matched, fps)
    if scenes and not a.no_game_filter:
        oog = parse_out_of_game(a.smoke); n0 = len(ev); ev = in_game_filter(ev, fps, n, to_t, oog, a.edge, max([x[1] for x in scenes]) + 40)
        print(f'вне игры отброшено {n0 - len(ev)} из {n0} (XMB/до старта, экраны загрузки и карточки, края записи {a.edge:.0f} с)', flush=True)
    total = len(ev); ev_all = list(ev)
    if len(ev) > a.top:   # съёмка с рук и муар дают шум: оставляем самые сильные (скачок x корень из числа блоков), порядок — по времени
        ev = sorted(sorted(ev, key=lambda e: -e['jump'] * e['blocks'] ** .5)[:a.top], key=lambda e: e['frame'])
        print(f'событий {total}, в отчёт взято {a.top} сильнейших (--top)', flush=True)
    want = {}
    for e in ev:
        for o in range(-3, 4): want[e['frame'] + o] = None
    frames = {}
    for e in ev:   # кадры -3..+3 берём перемоткой (полный второй проход по 26 минутам не нужен)
        i0 = e['frame'] - 3
        for k, f in enumerate(decode_rect(a.video, q, info, start=max(0, (i0 - .5) / fps), dur=8 / fps)):
            if i0 + k <= e['frame'] + 3: frames[i0 + k] = f.copy()
    os.makedirs(os.path.join(a.out, 'events'), exist_ok=True); rows = []
    for k, e in enumerate(ev, 1):
        s = scene_of(e['frame'], flashes, scenes, sk, matched) if scenes else (None, None, None)
        name, t0, f0 = s if s[0] else ('?', None, None)
        t_test = to_t(e['frame'] / fps) if to_t else (t0 + (e['frame'] - f0) / fps if t0 is not None else None)
        png = f'events/{k:03d}.png'; strip(frames, e).save(os.path.join(a.out, png))
        rows.append(dict(n=k, kind=e['kind'], scene=name, t_test=None if t_test is None else round(t_test, 2), video_s=round(e['frame'] / fps, 2), frame=e['frame'], box=e['box'], blocks=e['blocks'], jump=round(e['jump']), png=png))
    def _sc(e):
        s_ = scene_of(e['frame'], flashes, scenes, sk, matched) if scenes else (None, None, None)
        return dict(kind=e['kind'], scene=s_[0] or '?', t_test=round(to_t(e['frame'] / fps), 1) if to_t else None, video_s=round(e['frame'] / fps, 2), frame=e['frame'], blocks=e['blocks'], jump=round(e['jump']))
    json.dump(dict(video=a.video, fps=fps, frames=n, corners=q.tolist(), screen_score=score, flashes=flashes, scenes=scenes, events=rows, events_all=[_sc(e) for e in ev_all]), open(os.path.join(a.out, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(f'# Разбор видео {os.path.basename(a.video)}\n\nКадров {n}, {fps:.2f} к/с; вспышек сцен {len(flashes)}, сцен в smoke.txt {len(scenes)}'
                + ('' if not scenes or matched or len(scenes) - sk == len(flashes) else ' — **число не совпадает**, проверьте --skip-scenes и угол вспышки') + f'\n\nСобытий: {len(rows)}\n\n')
        if flashes:
            srows = [(j + 1, n, t, fr) for j, (fr, n, t) in enumerate(matched)] if matched else [(j + 1, scenes[j + sk][0] if scenes and j + sk < len(scenes) else '?', scenes[j + sk][1] if scenes and j + sk < len(scenes) else '?', fl) for j, fl in enumerate(flashes)]
            f.write('## Сцены\n\n| № | сцена | t начала, с | кадр вспышки | видео, с |\n|---|---|---|---|---|\n' + ''.join(f'| {j} | {n} | {t} | {fr} | {fr / fps:.2f} |\n' for j, n, t, fr in srows) + '\n')
        f.write('## События\n\n| № | вид | сцена | t теста, с | видео, с | кадр | блоков | скачок | картинка |\n|---|---|---|---|---|---|---|---|---|\n')
        for r in rows: f.write(f'| {r["n"]} | {r["kind"]} | {r["scene"]} | {r["t_test"]} | {r["video_s"]} | {r["frame"]} | {r["blocks"]} | {r["jump"]} | ![{r["n"]}]({r["png"]}) |\n')
    print(f'отчёт {a.out}/report.md: событий {len(rows)}', flush=True)
    return 0


# ---------------------------------------------------------------- самопроверка на синтетике
def homography(src, dst):
    A = []; b = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u); A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    h = np.linalg.solve(np.array(A, float), np.array(b, float)); return np.append(h, 1).reshape(3, 3)


def make_synth(path, flicker=True, popin=True, seed=1):
    """1920x1080, 60 к/с, 8 с: экран с перекосом на тёмном фоне, три сцены со вспышкой (tr 32 px) на кадрах 30/180/330; мигание (кадры 100-101) и pop-in (кадр 250)"""
    n = 480; yy, xx = np.mgrid[0:OH, 0:OW]
    base = (np.stack([(xx * 0.4 + yy * 0.2) % 256, (xx * 0.1 + 100) % 256, (yy * 0.5 + 50) % 256], 2)).astype(np.uint8)
    Q = [(560, 210), (1380, 250), (520, 830), (1420, 800)]          # TL TR BL BR экрана в кадре
    Hm = homography(Q, [(0, 0), (OW, 0), (0, OH), (OW, OH)])          # кадр -> экран
    gy, gx = np.mgrid[0:1080, 0:1920]; den = Hm[2, 0] * gx + Hm[2, 1] * gy + Hm[2, 2]
    sx = (Hm[0, 0] * gx + Hm[0, 1] * gy + Hm[0, 2]) / den; sy = (Hm[1, 0] * gx + Hm[1, 1] * gy + Hm[1, 2]) / den
    inside = (sx >= 0) & (sx < OW - 1) & (sy >= 0) & (sy < OH - 1); ix = sx.clip(0, OW - 1).astype(int); iy = sy.clip(0, OH - 1).astype(int)
    flash_at = {30, 180, 330}
    body = np.full((1080, 1920, 3), 150, np.uint8); body[(sx > -14) & (sx < OW + 14) & (sy > -14) & (sy < OH + 14)] = (12, 12, 12)   # корпус светлый, рамка экрана тёмная
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1920x1080', '-r', '60', '-i', '-',
                          '-c:v', 'libx264', '-crf', '8', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    for i in range(n):
        f = np.roll(base, i // 4, axis=1)                                         # медленный сдвиг картинки — «камера едет»
        f[0:56, 0:400] = (10, 10, 10); f[8:20, 8:120] = (200 + (i % 50), 40, 40)   # оверлей TEST17: тёмная подложка, текст меняется каждый кадр
        if any(i - k in flash_at for k in range(5)): f[4:44, 436:476] = 255   # метка TEST17: 40x40, 3 игровых кадра = 5-6 видео-кадров
        if flicker and i in (100, 101): f[150:174, 300:324] = (255, 0, 255)
        if popin and i >= 250: f[200:224, 100:124] = (0, 255, 0)
        fr = body.copy(); fr[inside] = f[iy[inside], ix[inside]]
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()


def selftest():
    d = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'vtr_selftest'); os.makedirs(d, exist_ok=True)
    smoke = os.path.join(d, 'smoke.txt'); open(smoke, 'w').write('SCENE alpha 0.0\nOVFLASH scene=alpha f=1 t=0.50 left=3\nSCENE beta 2.5\nOVFLASH scene=beta f=1 t=3.00 left=3\nSCENE gamma 5.0\nOVFLASH scene=gamma f=1 t=5.50 left=3\n')
    bad = 0
    for tag, fl, po in (('с дефектами', True, True), ('красный контроль: без дефектов', False, False)):
        v = os.path.join(d, f's_{int(fl)}.mp4'); make_synth(v, fl, po)
        a = argparse.Namespace(video=v, smoke=smoke, out=os.path.join(d, f'out_{int(fl)}'), corners=None, detect_only=False, flash_box=[436, 4, 476, 44], skip_scenes=0,
                               mask_overlay=[0, 0, .85, .21], thr=40., max_frac=.15, quiet=6, top=80, cache=None, index=None, timemap=None, edge=0., no_game_filter=True)
        shutil.rmtree(a.out, ignore_errors=True); review(a); r = json.load(open(os.path.join(a.out, 'report.json'))); kinds = [(e['kind'], e['frame'], e['scene']) for e in r['events']]
        print(tag, '-> вспышки', r['flashes'], 'события', kinds)
        ok_f = len(r['flashes']) == 3 and all(abs(x - y) <= 2 for x, y in zip(r['flashes'], (30, 180, 330)))
        has_fl = any(k == 'мигание' and abs(f - 100) <= 2 for k, f, _ in kinds); has_po = any(k == 'pop-in' and abs(f - 250) <= 2 for k, f, _ in kinds)
        if fl:
            if not (ok_f and has_fl and has_po): print('ПРОВАЛ: вспышки/мигание/pop-in не найдены'); bad += 1
            if not any(s == 'beta' for _, _, s in kinds if _ == 100) and not all(s in ('alpha', 'beta') for k, f, s in kinds if f == 100 or f == 101): print('ПРОВАЛ: сцена события'); bad += 1
        else:
            if not ok_f or kinds: print('ПРОВАЛ красного контроля: ложные события', kinds); bad += 1
    print('САМОПРОВЕРКА', 'OK' if not bad else 'ПРОВАЛ'); return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video', nargs='?'); ap.add_argument('--smoke'); ap.add_argument('--out', default=None)
    ap.add_argument('--corners', type=lambda s: [float(x) for x in s.split(',')]); ap.add_argument('--detect-only', action='store_true')
    ap.add_argument('--profile', choices=sorted(PROFILES), default='test18', help='метка сцены и оверлей сборки: test18 (метка 12x12 внизу слева, оверлей строкой внизу) или test17 (метка 40x40 справа вверху, оверлей сверху)'); ap.add_argument('--flash-box', type=lambda s: [float(x) for x in s.split(',')], default=None, help='x0,y0,x1,y1 метки сцены на 480x272 (TEST17: белый квадрат 40x40, правый верхний угол, 3 игровых кадра)')
    ap.add_argument('--skip-scenes', type=int, default=0); ap.add_argument('--mask-overlay', type=lambda s: [float(x) for x in s.split(',')], default=None, help='оверлей TEST17: подложка (0,0)-(W,56) на 480x272, W до ~400 px')
    ap.add_argument('--thr', type=float, default=40.); ap.add_argument('--max-frac', type=float, default=.15, help='доля блоков кадра, выше которой изменение считается сменой кадра'); ap.add_argument('--quiet', type=int, default=6, help='кадров после вспышки без событий')
    ap.add_argument('--timemap', help='JSON [[видео с, t теста], ...]: точная карта времени (точнее индекса)'); ap.add_argument('--edge', type=float, default=30., help='сколько секунд от начала и конца записи не смотреть'); ap.add_argument('--no-game-filter', action='store_true', help='не отбрасывать вне игры (меню, загрузки)'); ap.add_argument('--top', type=int, default=80, help='сколько сильнейших событий класть в отчёт'); ap.add_argument('--cache', help='файл .npy с блоками кадров: есть — не декодировать заново'); ap.add_argument('--index', help='ИНДЕКС.tsv от tools/video_split_scenes.py вместо поиска меток'); ap.add_argument('--selftest', action='store_true')
    a = apply_profile(ap.parse_args())
    if a.selftest: return selftest()
    if not a.video: ap.print_help(); return 2
    a.out = a.out or os.path.splitext(a.video)[0] + '_review'
    return review(a)


if __name__ == '__main__':
    sys.exit(main())
