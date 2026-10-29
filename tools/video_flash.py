#!/usr/bin/env python3
"""Всплески картинки на видео с PSP (прыжки текстур, pop-in, склейки) и привязка к логу железа.

  tools/video_flash.py VIDEO smoke.txt --out DIR [--crop x:y:w:h] [--anchors v:t,v:t,...] [--thr 6]

  VIDEO     любое видео (4K тоже: внутри уменьшается до 1280x720); экран PSP по умолчанию crop=160:70:980:520 (координаты 1280x720)
  smoke.txt лог железа (строки SCENE имя t, TELEPORT t=.. kind=goto|foot|repair)
  Что делает: разница соседних кадров экрана против медианы окна 17 кадров; всплеск = пик выше thr без скачка яркости.
  Время видео -> время игры (t лога): сначала по --anchors (видео_с:t игры, по двум-трём точкам из строки оверлея
  «tNNN.N» внизу кадра; игра на низком FPS идёт медленнее часов видео), иначе автоматом: сильные склейки видео
  выравниваются по началам сцен лога (SCENE/goto/foot), проверка — таблица привязки в DIR/привязка.txt.
  Выход: DIR/всплески.tsv (кадр · видео с · t игры · сцена · +с от начала сцены · сила · телепорт/нет),
  DIR/листы/NNN_кадр.png — до/после по каждому «не телепорту», DIR/сводка.txt.
  --scenario FILE (сценарий теста) — добавляет пометку «eye override»: моменты flag eyex (глаз камеры переставлен сценарием,
  скачок камеры в этих окнах — артефакт теста, не дефект игры); время считается от SCENE в логе плюс сумма wait/press.
  DIR/классы.tsv: у каждого «не телепорта» классы: gg переключался (GGSTAT, доля секунд с ggOn не 0 и не 100 % — смотреть базовую
  частоту в сводке, иначе совпадение случайно) · чтение io>15 мс · недогруз клеток (BB miss / >100) · камера: строки CAMIN
  (если CAMIN пишется посекундно — по секундам, иначе сводка сцены jmax) · eye override.
  Телепорт = в логе kind=goto или foot в пределах ±1,5 с игры от всплеска (repair — не телепорт, это починка).
"""
import shutil, argparse, os, re, subprocess, sys
import numpy as np

SW, SH = 245, 130


def _g(pat, ln):
    m = re.search(pat, ln)
    if not m: raise ValueError
    return m.group(1)


def read_gray(video, crop):
    x, y, w, h = crop
    vf = f'scale=1280:720,crop={w}:{h}:{x}:{y},scale={SW}:{SH},format=gray'
    p = subprocess.Popen(['nice', '-n', '10', 'ffmpeg', '-v', 'error', '-i', video, '-vf', vf, '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    out, n = [], SW * SH
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        out.append(np.frombuffer(b, np.uint8))
    p.wait()
    a = np.array(out, np.float32).reshape(-1, SH, SW)
    return a


def fps_of(video):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'): sys.exit('video_flash: нет ffmpeg/ffprobe в PATH')
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip().strip(',')
    try: a, b = r.split('/'); return float(a) / float(b)
    except (ValueError, ZeroDivisionError): sys.exit(f'video_flash: не удалось прочитать частоту кадров {video!r} (ffprobe вернул {r!r})')


def parse_log(path):
    scenes, tele = [], []
    for ln in open(path, encoding='utf-8', errors='replace'):
        if ln.startswith('SCENE '):
            m = re.match(r'SCENE (\S+) ([\d.]+)', ln)
            if m: scenes.append((float(m.group(2)), m.group(1)))
        elif ln.startswith('TELEPORT '):
            m = re.search(r't=([\d.]+) kind=(\w+)', ln)
            if m: tele.append((float(m.group(1)), m.group(2)))
    return scenes, tele


def spikes(a, thr):
    d = np.abs(np.diff(a, axis=0)).mean((1, 2)); lum = a.mean((1, 2)); dl = np.abs(np.diff(lum))
    pad = np.pad(d, 8, mode='edge')
    med = np.median(np.lib.stride_tricks.sliding_window_view(pad, 17), axis=1)
    sc = d - med
    out, last = [], -99
    for i in range(8, len(d) - 8):
        if sc[i] > thr and d[i] >= d[i - 1] and d[i] >= d[i + 1] and dl[i] < 6:
            if i - last > 15 or (out and sc[i] > out[-1][1] and i - out[-1][0] <= 15):
                if out and i - out[-1][0] <= 15: out[-1] = (i, sc[i])
                else: out.append((i, sc[i]))
            last = i
    return out


def eyex_times(scn, scenes):
    """моменты flag eyex в игровом времени: начало сцены из лога + сумма wait/press от строки scene"""
    st = {n: t for t, n in scenes}; out = []; cur = None; off = 0.0
    for ln in open(scn, encoding='utf-8', errors='replace'):
        w = ln.split()
        if not w or w[0].startswith('#'): continue
        if w[0] == 'scene' and len(w) > 1: cur = st.get(w[1]); off = 0.0
        elif w[0] == 'wait' and len(w) > 1: off += float(w[1])
        elif w[0] == 'flag' and len(w) > 1 and w[1] == 'eyex' and cur is not None: out.append(cur + off)
    return out


def classify(a, nt, scenes):
    import bisect
    gg, io, bb, cam, base = [], [], [], [], [0, 0]
    t = 0.0
    for ln in open(a.smoke, encoding='utf-8', errors='replace'):
        try:
            m = re.search(r'\bt=([\d.]+)', ln)
            if m and ln.startswith(('GGSTAT', 'SLOWFRAME', 'CAMIN', 'CAMCLIPSTAT', 'OVFLASH', 'PHSEC', 'RFAST')): t = float(m.group(1))
            if ln.startswith('GGSTAT'):
                f = int(_g(r'frames=(\d+)', ln)); o = int(_g(r'ggOn=(\d+)', ln)); gg.append((t, f, o)); base[1] += 1; base[0] += 0 < o < f
            elif ln.startswith('SLOWFRAME'):
                v = float(_g(r' io=([\d.]+)', ln))
                if v > 15: io.append(t)
            elif ln.startswith('BB '):
                m1 = re.search(r'miss (\d+)', ln); m2 = re.search(r'>100:(\d+)', ln)
                if (m1 and int(m1.group(1)) > 0) or (m2 and int(m2.group(1)) > 0): bb.append(t)
            elif ln.startswith('CAMIN'):
                fr = int(_g(r'frames=(\d+)', ln)); j = int(_g(r'jump=(\d+)', ln)); jm = float(_g(r'jmax=([\d.]+)', ln)); cam.append((t, fr, j, jm))
        except ValueError:
            continue
    camt = [c[0] for c in cam]
    eyes = eyex_times(a.scenario, scenes) if a.scenario else []
    with open(os.path.join(a.out, 'классы.tsv'), 'w', encoding='utf-8') as f:
        f.write('кадр\tвидео_с\tt_игры\tсцена\tплюс_с\tсила\tклассы\n')
        cnt = {}
        for r in nt:
            tg = r[2]; tags = []
            if any(0 < o < fr for tt, fr, o in gg if tg - 1 <= tt <= tg + 2): tags.append('gg переключался')
            if any(abs(x - tg) <= 1.0 for x in io): tags.append('чтение io>15мс')
            if any(abs(x - tg) <= 1.0 for x in bb): tags.append('недогруз клеток')
            k = bisect.bisect_left(camt, tg)
            if k < len(cam):
                tt, fr, j, jm = cam[k]
                if fr <= 40 and tt - 1.5 <= tg <= tt and jm >= 0.5: tags.append(f'камера jump {jm:.1f} м (посекундно)')
                elif fr > 40 and jm >= 1.0: tags.append(f'камера jmax {jm:.1f} м (сводка сцены)')
            if any(0 <= tg - x <= 3.0 or abs(tg - x) <= 1.0 for x in eyes): tags.append('eye override (flag eyex)')
            for x in tags: cnt[x.split(' ')[0] + ' ' + x.split(' ')[1] if x.startswith('gg') else x.split(' (')[0]] = cnt.get(x.split(' ')[0] + ' ' + x.split(' ')[1] if x.startswith('gg') else x.split(' (')[0], 0) + 1
            f.write(f'{r[0]}\t{r[1]:.1f}\t{r[2]:.1f}\t{r[3]}\t{r[4]:.1f}\t{r[5]:.0f}\t{"; ".join(tags) or "прочее"}\n')
    with open(os.path.join(a.out, 'сводка.txt'), 'a', encoding='utf-8') as f:
        f.write(f'классы (пересекаются): {cnt}; базовая частота секунд с ggOn не 0 и не 100 %: {base[0]}/{base[1]}\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('smoke'); ap.add_argument('--out', required=True)
    ap.add_argument('--crop', default='160:70:980:520', help='экран PSP x:y:w:h в координатах 1280x720')
    ap.add_argument('--anchors', default='', help='видео_с:t_игры через запятую (из строки оверлея)')
    ap.add_argument('--no-sheets', action='store_true', help='только таблицы (всплески.tsv, сводка, классы), без листов до/после'); ap.add_argument('--thr', type=float, default=6.0); ap.add_argument('--scenario', default='')
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, 'листы'), exist_ok=True)
    fps = fps_of(a.video)
    crop = [int(x) for x in a.crop.split(':')]
    st = os.stat(a.video); cache = os.path.join(a.out, 'screen_%s_%s_%d_%d.npy' % (os.path.basename(a.video).replace('.', '_'), '-'.join(map(str, crop)), st.st_size, int(st.st_mtime)))
    if os.path.exists(cache): g = np.load(cache)
    else: g = read_gray(a.video, crop); np.save(cache, g)
    if len(g) < 20: sys.exit(f'video_flash: в видео {len(g)} кадров (нужно 20 и больше)')
    sp = spikes(g, a.thr)
    scenes, tele = parse_log(a.smoke)
    starts = sorted({t for t, _ in scenes} | {t for t, k in tele if k in ('goto', 'foot')})
    if a.anchors:
        pairs = sorted((float(p.split(':')[0]), float(p.split(':')[1])) for p in a.anchors.split(','))
        how = 'заданы вручную'
    else:
        # старт: первая сильная склейка видео после начала = начало первой сцены с телепортом/загрузкой; пробуем разные первые пары
        strong = [i / fps for i, s in sp if s > 15]
        best = []
        for v0 in strong[:6]:
            for g0 in starts[:4]:
                lv, lg, rate = v0, g0, 1.2; pr = [(v0, g0)]
                for gg in [s for s in starts if s > g0]:
                    lo, hi = lv + (gg - lg) * 0.8 - 1.0, lv + (gg - lg) * 2.2 + 1.0
                    cand = [v for v in strong if lo <= v <= hi]
                    if not cand: continue
                    v = min(cand, key=lambda x: abs(x - (lv + (gg - lg) * rate)))
                    if gg - lg > 0.5: rate = 0.5 * rate + 0.5 * (v - lv) / (gg - lg)
                    pr.append((v, gg)); lv, lg = v, gg
                if len(pr) > len(best): best = pr
        pairs = best; how = f'ВНИМАНИЕ авто-привязка ненадёжна (проверьте привязка.txt, лучше --anchors по оверлею): авто: {len(pairs)} из {len(starts)} начал сцен лога сопоставлено со склейками видео (качество: {100 * len(pairs) // max(1, len(starts))} %)'
    with open(os.path.join(a.out, 'привязка.txt'), 'w', encoding='utf-8') as f:
        f.write(how + '\nвидео_с\tt_игры\n' + ''.join(f'{v:.2f}\t{t:.2f}\n' for v, t in pairs))
    if len(pairs) < 2: print('привязка не получилась: задайте --anchors', file=sys.stderr); return 1
    V = [p[0] for p in pairs]; T = [p[1] for p in pairs]
    tele_t = [t for t, k in tele if k in ('goto', 'foot')]
    rows = []
    for i, s in sp:
        v = i / fps; t = float(np.interp(v, V, T, left=None, right=None))
        if v < V[0]: t = T[0] - (V[0] - v) / 1.2
        if v > V[-1]: t = T[-1] + (v - V[-1]) / 1.2
        if t < 0: continue   # до начала сценария (заставка, меню, загрузка)
        sc = [x for x in scenes if x[0] <= t]; name, st = (sc[-1][1], sc[-1][0]) if sc else ('?', 0.0)
        tp = any(abs(t - x) <= 1.5 for x in tele_t) or any(abs(t - x[0]) <= 1.0 for x in scenes)
        rows.append((i, v, t, name, t - st, s, 'телепорт' if tp else 'нет'))
    with open(os.path.join(a.out, 'всплески.tsv'), 'w', encoding='utf-8') as f:
        f.write('кадр\tвидео_с\tt_игры\tсцена\tплюс_с_от_начала_сцены\tсила\tтелепорт\n')
        for r in rows: f.write(f'{r[0]}\t{r[1]:.1f}\t{r[2]:.1f}\t{r[3]}\t{r[4]:.1f}\t{r[5]:.1f}\t{r[6]}\n')
    nt = [r for r in rows if r[6] == 'нет']
    with open(os.path.join(a.out, 'сводка.txt'), 'w', encoding='utf-8') as f:
        f.write(f'{how}\nвсплесков {len(rows)}, телепорт сценария {len(rows) - len(nt)}, не телепорт {len(nt)}\n')
        for r in nt: f.write(f'  кадр {r[0]} видео {r[1]:.1f}с t{r[2]:.0f} {r[3]} +{r[4]:.1f}с сила {r[5]:.0f}\n')
    classify(a, nt, scenes)
    print(open(os.path.join(a.out, 'сводка.txt'), encoding='utf-8').read(), flush=True)
    # листы: до/после (полный кадр экрана из исходника). -ss до -i: быстрый переход, а не декод всего видео на каждый кадр
    if a.no_sheets: return 0
    from PIL import Image, ImageDraw
    for k, r in enumerate(nt):
        im = Image.new('RGB', (840, 238 + 18), 'black'); d = ImageDraw.Draw(im)
        for j, off in enumerate((-2, 1)):
            fn = os.path.join(a.out, '_t.png')
            if os.path.exists(fn): os.remove(fn)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0.0, (r[0] + off) / fps):.4f}', '-i', a.video, '-vf', f'scale=1280:720,crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]},scale=420:238', '-frames:v', '1', fn])
            if os.path.exists(fn): im.paste(Image.open(fn), (j * 420, 18))
        d.text((4, 3), f'кадр {r[0]} видео {r[1]:.1f}с t{r[2]:.0f} {r[3]} +{r[4]:.1f}с сила {r[5]:.0f} · до | после', fill='yellow')
        im.save(os.path.join(a.out, 'листы', f'{k + 1:03d}_{r[0]}.png'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
