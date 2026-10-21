#!/usr/bin/env python3
"""Выбор множителя наклона мипа земли (№539, TEST14) одной командой по снимкам сцены tests/groundbias/gen.sh.

Вход: папка со снимками PSP (shots/*.bmp, или png эмулятора) с именами gb<уровень>_<множитель без точки>_<NN> (12 снимков подряд при проезде 2 м/с)
и gb<уровень>_<множитель>_near (стоя). Множитель в имени: 10 = 1.0, 15 = 1.5, 20 = 2.0.

Метрики (яркость 0..255, по каждому множителю):
  мерцание дали  = среднее |HP(кадр i+1) − HP(кадр i)| по зоне дали (по умолчанию строки 0,38..0,58 высоты, колонки 0,25..0,75: дорога у горизонта),
                   HP = кадр минус его размытие σ 2 px (убирает медленный сдвиг картины от движения, оставляет зерно и муар); и то же, поделённое на
                   среднее |HP| (относительное: размытая даль мерцает меньше просто потому, что бледнее)
  мерцание бордюра = то же по зоне краёв дороги (по умолчанию строки 0,46..0,68, колонки 0,08..0,40 и 0,60..0,92 по обе стороны полосы: бордюр, тротуар,
                   угол тротуара с водостоком sdewlk_corner; №504 «бордюр рябит везде»)
  резкость ближней = дисперсия лапласиана в зоне ближней земли (строки 0,76..0,97, колонки 0,03..0,30 и 0,70..0,97: земля по бокам от машины), по снимку _near и по ряду
Выбор: наименьшая оценка = среднее (мерцание дали / у 1.0, мерцание бордюра / у 1.0) среди множителей, у которых резкость ближней не ниже SHARP_MIN (0,85) от
множителя 1.0 (базовый, текущая сборка). Если мерцание хоть одной зоны у кандидата выше, чем у 1.0, он отбрасывается (должно падать у дали и у бордюра).

  python3 tools/groundbias_pick.py SHOTDIR [--level 1] [--far y0,y1,x0,x1] [--curb y0,y1,xa0,xa1,xb0,xb1] [--near y0,y1] [--sharp-min 0.85] [--out compare.png]
  python3 tools/groundbias_pick.py --selftest
Печатает таблицу, строку «ВЫБОР: ...», пишет compare.png (ближняя земля и даль рядом по множителям, крупно: для глаза)."""
import argparse, re, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

SHARP_MIN = 0.85


def load(p):
    return Image.open(p).convert('RGB')


def lum(im):
    a = np.asarray(im, np.float32)
    return a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114


def hp(L):
    """кадр минус размытие σ 2 px (высокие частоты)"""
    im = Image.fromarray(np.clip(L, 0, 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(2))
    return L - np.asarray(im, np.float32)


def lap_var(L):
    c = L[1:-1, 1:-1]
    lap = L[:-2, 1:-1] + L[2:, 1:-1] + L[1:-1, :-2] + L[1:-1, 2:] - 4 * c
    return float(lap.var())


def roi(L, y0, y1, x0, x1):
    h, w = L.shape
    return L[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]


def find_series(d, level):
    """-> {множитель(float): ([пути ряда по порядку], путь_near или None)}"""
    out = {}
    for p in sorted(Path(d).iterdir()):
        m = re.fullmatch(r'gb%s_(\d+)_(\d+|near)\.(bmp|png)' % level, p.name, re.I)
        if not m: continue
        k = int(m.group(1)) / 10.0
        s = out.setdefault(k, ([], None))
        if m.group(2).lower() == 'near': out[k] = (s[0], p)
        else: s[0].append(p)
    return out


def analyse(series, far, near_y, curb):
    fy0, fy1, fx0, fx1 = far
    cy0, cy1, ca0, ca1, cb0, cb1 = curb
    ny0, ny1 = near_y
    res = {}
    for k, (frames, near) in sorted(series.items()):
        Ls = [lum(load(p)) for p in frames]
        hps = [hp(roi(L, fy0, fy1, fx0, fx1)) for L in Ls]
        d = [float(np.abs(hps[i + 1] - hps[i]).mean()) for i in range(len(hps) - 1)]
        cps = [(hp(roi(L, cy0, cy1, ca0, ca1)), hp(roi(L, cy0, cy1, cb0, cb1))) for L in Ls]
        dc = [float((np.abs(cps[i + 1][0] - cps[i][0]).mean() + np.abs(cps[i + 1][1] - cps[i][1]).mean()) / 2) for i in range(len(cps) - 1)]
        energy = float(np.mean([np.abs(h).mean() for h in hps])) if hps else float('nan')
        def sharp(L):
            return (lap_var(roi(L, ny0, ny1, .03, .30)) + lap_var(roi(L, ny0, ny1, .70, .97))) / 2
        sn = sharp(lum(load(near))) if near else float('nan')
        ss = float(np.mean([sharp(L) for L in Ls])) if Ls else float('nan')
        res[k] = dict(n=len(Ls), flick=float(np.mean(d)) if d else float('nan'), curb=float(np.mean(dc)) if dc else float('nan'), energy=energy,
                      rel=(float(np.mean(d)) / energy) if d and energy > 1e-6 else float('nan'), sharp_near=sn, sharp_series=ss,
                      near=near, first=frames[0] if frames else None)
    return res


def pick(res, sharp_min):
    if 1.0 not in res: base = None
    else: base = res[1.0]['sharp_near'] if res[1.0]['sharp_near'] == res[1.0]['sharp_near'] else res[1.0]['sharp_series']
    ok = []
    for k, r in sorted(res.items()):
        s = r['sharp_near'] if r['sharp_near'] == r['sharp_near'] else r['sharp_series']
        r['sharp_rel'] = (s / base) if base else float('nan')
        if base is None or r['sharp_rel'] >= sharp_min: ok.append(k)
    b = res.get(1.0)
    for k, r in res.items():
        r['score'] = float('nan')
        if b and b['flick'] > 1e-9 and b['curb'] > 1e-9 and r['flick'] == r['flick'] and r['curb'] == r['curb']:
            r['score'] = (r['flick'] / b['flick'] + r['curb'] / b['curb']) / 2
    cand = [k for k in ok if res[k]['score'] == res[k]['score'] and (k == 1.0 or (res[k]['flick'] <= b['flick'] and res[k]['curb'] <= b['curb']))]
    return (min(cand, key=lambda k: res[k]['score']) if cand else None), base


def compare_png(res, far, near_y, curb, out):
    tiles = []
    for k, r in sorted(res.items()):
        if not r['near'] or not r['first']: continue
        a, b = load(r['near']), load(r['first'])
        w, h = a.size
        na = a.crop((0, int(h * near_y[0]), w, int(h * near_y[1]))).resize((w * 2, int(h * (near_y[1] - near_y[0])) * 2), Image.NEAREST)
        fb = b.crop((int(w * far[2]), int(h * far[0]), int(w * far[3]), int(h * far[1])))
        fb = fb.resize((fb.width * 4, fb.height * 4), Image.NEAREST)
        cb = b.crop((int(w * curb[2]), int(h * curb[0]), int(w * curb[3]), int(h * curb[1])))
        cb = cb.resize((cb.width * 3, cb.height * 3), Image.NEAREST)
        t = Image.new('RGB', (max(na.width, fb.width, cb.width), na.height + fb.height + cb.height + 16), (0, 0, 0))
        ImageDraw.Draw(t).text((4, 2), 'x%.2f ближняя / даль / бордюр (левый край дороги)' % k, fill=(255, 255, 255))
        t.paste(na, (0, 16)); t.paste(fb, (0, 16 + na.height)); t.paste(cb, (0, 16 + na.height + fb.height)); tiles.append(t)
    if not tiles: return False
    W = sum(t.width for t in tiles) + 8 * (len(tiles) - 1); H = max(t.height for t in tiles)
    sheet = Image.new('RGB', (W, H), (40, 40, 40)); x = 0
    for t in tiles: sheet.paste(t, (x, 0)); x += t.width + 8
    sheet.save(out); return True


def report(res, chosen, base):
    print('множитель  кадров  мерцание_дали  относит.  мерцание_бордюра  оценка  резкость_near  к_базе  резкость_ряда')
    for k, r in sorted(res.items()):
        print('%8.2f  %6d  %13.3f  %8.3f  %16.3f  %6.2f  %13.1f  %6.2f  %13.1f' % (k, r['n'], r['flick'], r['rel'], r['curb'], r.get('score', float('nan')), r['sharp_near'], r.get('sharp_rel', float('nan')), r['sharp_series']))
    if chosen is None: print('ВЫБОР: нет (нет ряда снимков или все множители режут резкость ближней ниже порога)')
    else: print('ВЫБОР: %.2f (даль %.3f против %.3f у 1.0, бордюр %.3f против %.3f, резкость ближней %.2f от базы)' % (
        chosen, res[chosen]['flick'], res.get(1.0, {}).get('flick', float('nan')), res[chosen]['curb'], res.get(1.0, {}).get('curb', float('nan')), res[chosen].get('sharp_rel', float('nan'))))


def selftest():
    import tempfile, random
    d = Path(tempfile.mkdtemp()); rng = np.random.RandomState(1)
    W, H = 480, 272
    yy, xx = np.mgrid[0:H, 0:W]
    for lv, mul, amp, blur in ((1, 10, 30, 0.0), (1, 15, 18, 0.6), (1, 20, 10, 1.2)):
        for i in range(13):   # 12 + near
            base = 120 + 60 * np.sin(xx / 3.0) * (yy > H * .75)            # ближняя земля: рисунок
            far = 110 + amp * np.sin(xx / 2.0 + i * 1.3) * ((yy > H * .38) & (yy < H * .6))   # даль: муар, фаза гуляет от кадра к кадру
            a = np.clip(base + far - 110, 0, 255)
            im = Image.fromarray(np.stack([a, a, a], -1).astype(np.uint8))
            if blur: im = im.filter(ImageFilter.GaussianBlur(blur * (0.0 if False else 1)))
            im.save(d / ('gb1_%d_%s.bmp' % (mul, 'near' if i == 12 else '%02d' % (i + 1))))
    series = find_series(d, 1); res = analyse(series, (.38, .58, .25, .75), (.76, .97), (.46, .68, .08, .40, .60, .92))
    chosen, base = pick(res, SHARP_MIN); report(res, chosen, base)
    ok = chosen in (1.5, 2.0) and res[1.0]['flick'] > res[1.5]['flick'] > res[2.0]['flick']
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dir', nargs='?'); ap.add_argument('--level', default='1')
    ap.add_argument('--far', default='0.38,0.58,0.25,0.75'); ap.add_argument('--near', default='0.76,0.97')
    ap.add_argument('--curb', default='0.46,0.68,0.08,0.40,0.60,0.92')
    ap.add_argument('--sharp-min', type=float, default=SHARP_MIN); ap.add_argument('--out', default='groundbias_compare.png')
    ap.add_argument('--selftest', action='store_true'); a = ap.parse_args()
    if a.selftest: return selftest()
    if not a.dir: ap.error('нужна папка со снимками')
    far = tuple(float(v) for v in a.far.split(',')); near_y = tuple(float(v) for v in a.near.split(','))
    series = find_series(a.dir, a.level)
    if not series: print('нет снимков gb%s_<множитель>_<NN>.bmp|png в %s' % (a.level, a.dir)); return 2
    curb = tuple(float(v) for v in a.curb.split(','))
    res = analyse(series, far, near_y, curb); chosen, base = pick(res, a.sharp_min); report(res, chosen, base)
    print('сводный снимок:', a.out if compare_png(res, far, near_y, curb, a.out) else 'нет (нужны _near и ряд)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
