#!/usr/bin/env python3
"""Полоса «Трассы» автоисследователя: тяжесть кадра PSP по следам ботов и снимки вида для находок (интерфейс: tools/autoexplore/INTERFACE.md).
  tracks.py frames --run build/autoexplore/<прогон> [--level-dir ПАКЕТ] [--variant new] [--shots 12]
      читает <прогон>/trace/L<n>_s<seed>.tsv (формат trace.tsv ночи), считает кадр PSP на каждой секунде (frame_model.py), пишет
      <прогон>/findings/tracks_L<n>_s<seed>.tsv строками heavy_frame (>31 мс) и overload_long (>=10 с подряд) и снимки в <прогон>/shots/
  tracks.py snap --run build/autoexplore/<прогон> [--level-dir ПАКЕТ] [--limit 200] [FILE ...]
      по строкам findings любой полосы (по умолчанию все <прогон>/findings/*.tsv) снимает вид в точке находки: если курса нет, лист 2x2 по четырём курсам;
      индекс <прогон>/shots/index.tsv: файл<TAB>строка<TAB>png. Строки findings не меняются (файлы только дописываются)
Колонки находки: level x y z type weight seed frame description. Курс из trace (колонка heading, рад) или по смещению за соседние секунды."""
import argparse, glob, math, os, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import frame_model as FM
def level_path(pkg, lv):
    if lv < 1 or lv > 7: return None
    p = Path(pkg) / ('level.shr' if lv == 1 else f'l{lv}/level.shr'); return p if p.exists() else None
def latest_pkg():
    c = sorted(d for d in glob.glob(str(HERE.parents[3] / 'build/final-2*')) + glob.glob(os.path.expanduser('~/Downloads/shar-psp-sonnet-runs-w/build/final-2*')) if os.path.isdir(d) and 'release' not in d)
    return c[-1] if c else None
_shooters = {}
def shooter(path):
    import hostshot as HS
    if str(path) not in _shooters: _shooters[str(path)] = HS.Shooter(path)
    return _shooters[str(path)]
def heading_of(tr, i):
    if 'heading' in tr: return float(tr['heading'][i])
    n = len(tr['x'])
    for k in range(1, 6):
        a, b = max(0, i - k), min(n - 1, i + k); dx, dz = tr['x'][b] - tr['x'][a], tr['z'][b] - tr['z'][a]
        if math.hypot(dx, dz) > 1.5: return math.atan2(dx, dz)
    return 0.0
def clean(s): return re.sub(r'[\t\r\n]+', ' ', s)
def frames(a):
    run = Path(a.run); pkg = a.level_dir or latest_pkg(); out_f = run / 'findings'; out_f.mkdir(parents=True, exist_ok=True); shots = run / 'shots'; shots.mkdir(exist_ok=True)
    total = 0
    for tf in sorted(glob.glob(str(run / 'trace' / 'L*_s*.tsv'))):
        m = re.match(r'L(\d+)_s(\d+)\.tsv$', os.path.basename(tf))
        if not m: continue
        lv, seed = int(m.group(1)), int(m.group(2)); lp = level_path(pkg, lv)
        if not lp: print(f'{os.path.basename(tf)}: нет данных уровня {lv} в {pkg}, пропущен'); continue
        tr = FM.read_trace(tf); tbl = FM.city_table(lp, run / 'cache'); s = FM.series(tr, lv, tbl, a.variant); cpu = s['cpu']; n = len(cpu); over = cpu > 31.0
        pol = ((tr.get('heat', np.zeros(n)) > 0) | (tr.get('ai_chase', np.zeros(n)) > 0))
        finds = []; i = 0
        while i < n:   # подряд идущие секунды выше 31 мс — одна находка в самой тяжёлой точке
            if not over[i]: i += 1; continue
            j = i
            while j + 1 < n and over[j + 1]: j += 1
            k = i + int(np.argmax(cpu[i:j + 1])); dur = j - i + 1; mx = float(cpu[k])
            w = int(max(1, min(10, round(1 + (mx - 31) / 1.5 + dur / 4.0)))); typ = 'overload_long' if dur >= 10 else 'heavy_frame'
            parts = {'город': FM.K_KT * s['kt'][k], 'ИИ-машины': FM.K_AI * s['ai'][k], 'трафик': FM.K_TRF * s['trc'][k], 'разрушения': FM.K_BOOM * s['de'][k]}; top = max(parts, key=parts.get)
            d = (f'{"под полицией" if pol[k] else "обычная игра"}; кадр {mx:.1f} мс (модель PSP, вариант {a.variant}), {dur} с подряд выше 31; город {s["kt"][k]:.0f} тыс. треуг. ({parts["город"]:.1f} мс), '
                 f'ИИ {s["ai"][k]:.0f}, трафик {s["trc"][k]:.0f}, дальность {s["dd"][k]:.0f} м; главное: {top}; t={tr["t"][k]:.0f} с')
            finds.append(dict(i=i, k=k, lv=lv, x=tr['x'][k], y=tr['y'][k], z=tr['z'][k], typ=typ, w=w, seed=seed, frame=int(tr['t'][k] * 60), desc=d, h=heading_of(tr, k)))
            i = j + 1
        finds.sort(key=lambda f: (-f['w'], -f['frame']))
        for rank, f in enumerate(finds):
            if rank < a.shots and not a.no_shots:
                png = shots / f'L{lv}_s{seed}_{f["frame"]}_{f["typ"]}.png'
                try:
                    S = shooter(lp); gy = S.ground(f['x'], f['z'], f['y']); S.shot(f['x'], gy if gy is not None else f['y'], f['z'], f['h'], str(png), f'L{lv} s{seed} {f["typ"]}', 'normal')
                    f['desc'] += f'|снимок={png}'
                except Exception as e: f['desc'] += f'|снимок=ошибка {type(e).__name__}'
        outp = out_f / f'tracks_L{lv}_s{seed}.tsv'
        with open(outp, 'w') as o:   # файл полосы Трассы пересчитывается целиком (его пишет только эта полоса)
            for f in finds: o.write('\t'.join([str(f['lv']), '%.1f' % f['x'], '%.1f' % f['y'], '%.1f' % f['z'], f['typ'], str(f['w']), str(f['seed']), str(f['frame']), clean(f['desc'])]) + '\n')
        print(f'{os.path.basename(tf)}: {n} с, выше 31 мс {int(over.sum())}, находок {len(finds)} -> {outp.name}'); total += len(finds)
    print('находок всего', total)
def snap(a):
    run = Path(a.run); pkg = a.level_dir or latest_pkg(); shots = run / 'shots'; shots.mkdir(parents=True, exist_ok=True)
    files = a.files or sorted(glob.glob(str(run / 'findings' / '*.tsv'))); idx = open(shots / 'index.tsv', 'a'); done = 0
    from PIL import Image
    for fn in files:
        for ln, line in enumerate(open(fn), 1):
            p = line.rstrip('\n').split('\t')
            if len(p) < 9: continue
            try: lv, x, y, z = int(p[0]), float(p[1]), float(p[2]), float(p[3])
            except ValueError: continue
            lp = level_path(pkg, lv)
            if not lp or 'снимок=' in p[8]: continue
            S = shooter(lp); gy = S.ground(x, z, y); yy = gy if gy is not None and abs(gy - y) < 6 else y; typ = p[4]; mode = 'holes' if typ in ('hole', 'void_edge') else 'normal'
            ims = []; hs = [0.0, 1.5708, 3.1416, 4.7124]
            for h in hs:
                tmp = shots / '_t.png'; S.shot(x, yy, z, h, str(tmp), f'{typ} h={h:.2f}', mode); ims.append(Image.open(tmp).copy())
            sheet = Image.new('RGB', (ims[0].width * 2, ims[0].height * 2))
            for q, im in enumerate(ims): sheet.paste(im, ((q % 2) * im.width, (q // 2) * im.height))
            sheet = sheet.resize((sheet.width // 2, sheet.height // 2)); png = shots / f'L{lv}_{typ}_{x:.0f}_{z:.0f}_{p[7]}_{Path(fn).stem}_{ln}.png'; sheet.save(png)
            idx.write(f'{fn}\t{ln}\t{png}\n'); idx.flush(); done += 1
            if done >= a.limit: break
        if done >= a.limit: break
    try: os.remove(shots / '_t.png')
    except OSError: pass
    print('снимков', done)
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('frames'); f.add_argument('--run', required=True); f.add_argument('--level-dir'); f.add_argument('--variant', default='new', choices=['now', 'hybrid', 'new']); f.add_argument('--shots', type=int, default=12); f.add_argument('--no-shots', action='store_true')
    s = sub.add_parser('snap'); s.add_argument('--run', required=True); s.add_argument('--level-dir'); s.add_argument('--limit', type=int, default=200); s.add_argument('files', nargs='*')
    a = ap.parse_args(); {'frames': frames, 'snap': snap}[a.cmd](a)
