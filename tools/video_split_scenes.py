#!/usr/bin/env python3
"""Нарезка видео TEST17 на сцены по меткам (OVFLASH): быстрый шаг перед разбором tools/video_test_review.py.

  tools/video_split_scenes.py VIDEO --smoke smoke.txt --corners x0,y0,x1,y1,x2,y2,x3,y3 --out DIR [--no-cut]
    VIDEO — любое видео (лучше уменьшенная копия 1280x720), углы экрана TL TR BL BR в пикселях ЭТОГО видео.
    Читает только маленький кусок кадра у метки сцены (ffmpeg crop), метки сопоставляет с OVFLASH из smoke.txt по времени.
    -> DIR/ИНДЕКС.tsv (номер · сцена · начало и конец в видео, с · t теста начала · кадры) и DIR/scenes/NNN_<сцена>.mp4
    --no-cut — только индекс. Клип нарезается с пересжатием (точно по кадру), nice 20, готовые клипы не пересоздаются.
"""
import argparse, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_test_review as V


def flash_luma(path, q, info, box):
    """яркость метки по кадрам: crop вокруг центра метки в координатах видео"""
    H = V.homography([(0, 0), (V.OW, 0), (0, V.OH), (V.OW, V.OH)], [tuple(p) for p in q])
    x0, y0, x1, y1 = box; m = (x1 - x0) // 4
    pts = []
    for x, y in ((x0 + m, y0 + m), (x1 - m, y0 + m), (x0 + m, y1 - m), (x1 - m, y1 - m)):
        v = H @ np.array([x, y, 1.0]); pts.append(v[:2] / v[2])
    pts = np.array(pts); cx0, cy0 = pts.min(0).astype(int); cx1, cy1 = pts.max(0).astype(int)
    w, h = max(4, (cx1 - cx0) // 2 * 2), max(4, (cy1 - cy0) // 2 * 2)
    p = subprocess.Popen(['nice', '-n', '20', 'ffmpeg', '-v', 'error', '-i', path, '-vf', f'crop={w}:{h}:{cx0}:{cy0},scale=4:4,format=gray', '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE)
    out = []
    while True:
        b = p.stdout.read(16)
        if len(b) < 16: break
        out.append(float(np.frombuffer(b, np.uint8).mean()))
    p.wait(); return np.array(out)


def find_marks(a, fps, rise=45, lo=30):
    """метка = рост яркости патча на rise и выше относительно медианы до неё, держится 3-10 кадров и возвращается; не зависит от абсолютной яркости фона"""
    n = len(a); out = []; i = 14
    while i < n - 16:
        base = np.median(a[i - 13:i - 3])
        if a[i] - base >= rise and a[i - 1] - base < rise:
            L = 0
            while i + L < n and a[i + L] >= base + lo: L += 1
            if 3 <= L <= 45:   # при загрузке игра идёт медленно: 3 игровых кадра метки тянутся до 45 видеокадров
                after = np.median(a[i + L + 2:i + L + 10])
                if after < a[i] - 25 and abs(after - base) < 60: out.append(i); i += L + 20; continue
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('--smoke', required=True); ap.add_argument('--out', required=True); ap.add_argument('--no-cut', action='store_true')
    ap.add_argument('--corners', required=True, type=lambda s: [float(x) for x in s.split(',')])
    ap.add_argument('--flash-box', type=lambda s: [float(x) for x in s.split(',')], default=None)
    ap.add_argument('--profile', choices=sorted(V.PROFILES), default='test18', help='метка сцены: test18 (внизу слева) или test17 (справа вверху)')
    ap.add_argument('--reuse-luma', action='store_true', help='взять OUT/flash_luma.npy от прошлого прохода')
    a = V.apply_profile(ap.parse_args())
    info = V.probe(a.video); fps = info['fps']; q = np.array(a.corners, float).reshape(4, 2)
    os.makedirs(os.path.join(a.out, 'scenes'), exist_ok=True)
    lf = os.path.join(a.out, 'flash_luma.npy')
    lum = np.load(lf) if a.reuse_luma and os.path.exists(lf) else flash_luma(a.video, q, info, a.flash_box); n = len(lum); print(f'кадров {n}, {fps:.2f} к/с', flush=True)
    np.save(lf, lum)
    flashes = find_marks(lum, fps)
    scenes, ov = V.parse_smoke(a.smoke); matched, lost = V.match_flashes(flashes, fps, ov)
    print(f'метка: вспышек в видео {len(flashes)}, OVFLASH в логе {len(ov)} сцен, сопоставлено {len(matched)}, без пары {lost}', flush=True)
    # сцены без найденной метки (экран загрузки метку не показывает, на светлом небе она тонет): начало оцениваем по соседним найденным.
    # До загрузки и сама загрузка — вперёд от предыдущей метки (t лога = реальному времени), после загрузки — назад от следующей (загрузка тянется в реальном времени дольше)
    idx = {id_: k for k, id_ in enumerate([(o[0], o[1]) for o in ov])}
    anchors = {}
    for fr, name, t in matched: anchors[idx[(name, t)]] = fr / fps
    starts = []; kinds = []
    keys = sorted(anchors)
    for k, (name, t) in enumerate(ov):
        if k in anchors: starts.append(anchors[k]); kinds.append('метка'); continue
        pa = max([x for x in keys if x < k], default=None); nb = min([x for x in keys if x > k], default=None)
        loaded = any('_load' in ov[x][0] for x in range(pa if pa is not None else 0, k + 1))   # между предыдущей меткой и этой сценой была загрузка
        if pa is not None and (not loaded or nb is None): v = anchors[pa] + (t - ov[pa][1])
        elif nb is not None: v = anchors[nb] - (ov[nb][1] - t)
        else: v = 0.0
        starts.append(v); kinds.append('оценка')
    tt = n / fps; rows = []
    for k, (name, t) in enumerate(ov):
        st = starts[k]; en = starts[k + 1] if k + 1 < len(starts) else tt
        if en <= st: en = st + 1.0
        rows.append((k + 1, name, st, en, t, int(st * fps), int((en - st) * fps), kinds[k]))
    with open(os.path.join(a.out, 'ИНДЕКС.tsv'), 'w', encoding='utf-8') as f:
        f.write('№\tсцена\tначало_видео_с\tконец_видео_с\tt_теста_начала\tкадр_начала\tкадров\tточность\tфайл\n')
        for r in rows: f.write(f'{r[0]}\t{r[1]}\t{r[2]:.3f}\t{r[3]:.3f}\t{r[4]:.2f}\t{r[5]}\t{r[6]}\t{r[7]}\tscenes/{r[0]:03d}_{r[1]}.mp4\n')
    print(f'сцен с меткой {len(matched)}, с оценкой {len(rows) - len(matched)}', flush=True)
    print(f'индекс: {a.out}/ИНДЕКС.tsv ({len(rows)} сцен)', flush=True)
    if a.no_cut: return 0
    for r in rows:
        fn = os.path.join(a.out, 'scenes', f'{r[0]:03d}_{r[1]}.mp4')
        if os.path.exists(fn) and os.path.getsize(fn) > 1000: continue
        subprocess.run(['nice', '-n', '20', 'ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, r[2] - (0 if r[7] == "метка" else 1.5)):.3f}', '-i', a.video, '-t', f'{r[3] - r[2] + (0 if r[7] == "метка" else 3.0):.3f}', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', fn + '.tmp.mp4'], check=True)
        os.replace(fn + '.tmp.mp4', fn)
    print('клипы готовы', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
