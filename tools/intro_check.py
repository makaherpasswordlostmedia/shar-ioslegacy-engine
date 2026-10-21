"""Гейт интро в эмуляторе (tools/intro_gate.sh): smoke.txt и снимки прогона по tools/intro_scenario.txt.
  python tools/intro_check.py RUN_DIR [--data DIR] [--copy DIR] [--expect-fail K1,K2]
  RUN_DIR = build/smoke/<время> (smoke.txt + снимки окна), DIR = где EBOOT и movies/
  (1) пять роликов открылись по порядку без ошибок; radlogo доигран целиком: показано + пропущено = кадрам заголовка RMV,
      звука ушло ровно кадры*1764, время ролика 4,04 с ±0,25 с; остальные пропущены START (skip=1)
  (2) три снимка INTROSHOT: кадр окна против того же кадра RMV, разжатого ffmpeg на Маке (отпечаток 45x34 по середине
      картинки 4:3, средняя разница ≤ TOL из 255); отрицательный контроль — тот же снимок против кадра другого ролика
      обязан разойтись (> TOL): иначе сверка ничего не различает
  (2б) [sides] правка Роба 49 (пересмотр 32): поля по бокам — фон из того же кадра (movie_export.ambient), рамки поверх
      нет: поля снимка = полям эталона (средняя разница ≤ TOL_SIDE); красное — «flag tvframe» (рамка правки 32 поверх)
  (2в) [layout] ролики в DIR/movies: место картинки в заголовке SMV = movie_export.picture() и картинка не растянута
      (w/h = 4/3 ±1 %); красное — прежние ролики правки 32 (окно рамки, картинка шире 4:3)
  (3) START короче: вход в меню (строка MENU) раньше суммы длительностей роликов (87,4 с)
  (4) куча до и после интро одна: used и наибольший блок ±64 КБ
--copy DIR: снимки 480x272 (кадр без рамки окна) и эталоны рядом -> DIR/intro_<имя>.png
Код выхода 0 = PASS; первая строка вывода — итог.
"""
import argparse, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import movie_export as mx

TOL = 8.0
TOL_SIDE = 12.0   # поля (размытый фон) снимка против эталона ffmpeg + movie_export.ambient
CLIPS = mx.INTRO
NEG = {'vuglogo': ('foxlogo', 200), 'foxlogo': ('intro', 300), 'intro': ('foxlogo', 100)}   # чужой кадр для контроля
MEM = 64 << 10


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def window_frame(p):   # снимок окна PPSSPP: заголовок сверху, кадр 480x272 снизу
    im = Image.open(p).convert('RGB'); w, h = im.size; ch = min(h, round(w * 272 / 480))
    return im.crop((0, h - ch, w, h)).resize((480, 272), Image.LANCZOS)


def thumb(a):   # отпечаток середины картинки ролика (без 8 px у краёв) -> 45x34 средним по блокам
    x, y, w, h = mx.picture()
    im = Image.fromarray(np.asarray(a)[y + 8:y + h - 8, x + 8:x + w - 8]).resize((45, 34), Image.BOX)
    return np.asarray(im, np.float32)


_TV = None
def framed(ref):   # правка Роба 89: эталон с той же рамкой меню поверх (у её окна полупрозрачный блик стекла, как в меню)
    global _TV
    if mx.LAYOUT != 'menu': return ref
    if _TV is None:
        import ui_export as U
        _TV = U.widescreen_tvframe(U.all_images()['tvframe.png'], U.DST_W, U.DST_H, U.S).convert('RGBA')
    base = Image.fromarray(np.asarray(ref)).convert('RGBA'); base.alpha_composite(_TV)
    return np.asarray(base.convert('RGB'))


def sides(a):   # поля по бокам картинки (без 2 px у её краёв) -> отпечаток 2 x (12x34)
    x, _, w, _ = mx.picture(); a = np.asarray(a)
    if mx.LAYOUT == 'menu':   # правка Роба 89: поверх рамка меню — поля сверяются внутри её окна (размытый тот же кадр)
        x0, y0, x1, y1 = mx.menu_opening(); y0 += 2; y1 -= 2
        return [np.asarray(Image.fromarray(np.ascontiguousarray(b)).resize((12, 34), Image.BOX), np.float32)
                for b in (a[y0:y1, x0 + 2:max(x0 + 3, x - 2)], a[y0:y1, x + w + 2:max(x + w + 3, x1 - 2)])]
    return [np.asarray(Image.fromarray(np.ascontiguousarray(b)).resize((12, 34), Image.BOX), np.float32)
            for b in (a[:, :max(1, x - 2)], a[:, x + w + 2:])]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--copy'); ap.add_argument('--data')
    ap.add_argument('--expect-fail', default=''); a = ap.parse_args(); keyed = set()
    run = Path(a.run); lines = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    bad, info = [], []
    intro = [kv(l) for l in lines if l.startswith('INTRO ')]
    shots = [kv(l) for l in lines if l.startswith('INTROSHOT ')]
    mem = {l.split()[1]: kv(l) for l in lines if l.startswith('INTROMEM ')}
    menu = [kv(l) for l in lines if l.startswith('MENU ')]
    # (1) ролики
    if [int(d.get('clip', -1)) for d in intro] != list(range(len(CLIPS))): bad.append(f'роликов в журнале {len(intro)} из {len(CLIPS)} (или не по порядку)')
    for d in intro:
        c = CLIPS[int(d['clip'])]; e = int(d['err']); fr = int(d['frames'])
        info.append(f"{c}: кадров {d['shown']}+{d['dropped']}/{fr} опозд {d['late']} тишина {d['under']} разжатие ≤{d['dec']} мс "
                    f"чтение ≤{d['read']} мс {d['kbs']} КБ/с шаг {d['stride']} skip={d['skip']} {d['ms']} мс")
        if e: bad.append(f'{c}: ошибка {e}')
        hdr = mx.rmv_parse((mx.SRC / f'{c}.rmv').read_bytes(), c)['frames']
        if fr != hdr: bad.append(f'{c}: кадров в файле {fr} != RMV {hdr}')
        if c == 'radlogo':
            if int(d['skip']): bad.append('radlogo пропущен, а должен доиграть')
            if int(d['shown']) + int(d['dropped']) != hdr: bad.append(f"radlogo: показано+пропущено {int(d['shown']) + int(d['dropped'])} != {hdr}")
            if int(d['audio']) != hdr * mx.SPF: bad.append(f"radlogo: звука {d['audio']} != {hdr * mx.SPF}")
            if abs(int(d['ms']) - hdr * 40) > 250: bad.append(f"radlogo: {d['ms']} мс != {hdr * 40} ±250")
        elif not int(d['skip']): bad.append(f'{c}: START не пропустил')
    # (2) снимки против ffmpeg
    if len(shots) != 3: bad.append(f'снимков INTROSHOT {len(shots)} != 3')
    for s in shots:
        c = CLIPS[int(s['clip'])]; f = int(s['frame']); p = run / f"{s['name']}.png"
        if not p.exists() or f < 0: bad.append(f'{c}: нет снимка {p.name} или кадра'); continue
        got = window_frame(p); ref = framed(mx.reference_frame(c, f)); nc, nf = NEG.get(c, ('radlogo', 50))
        neg = framed(mx.reference_frame(nc, nf))
        d0 = float(np.abs(thumb(got) - thumb(ref)).mean()); dn = float(np.abs(thumb(got) - thumb(neg)).mean())
        info.append(f'{c} кадр {f}: разница {d0:.2f} (≤ {TOL}); контроль {nc} кадр {nf}: {dn:.2f} (> {TOL})')
        if d0 > TOL: bad.append(f'{c} кадр {f}: снимок != ffmpeg ({d0:.2f} > {TOL})')
        ds = max(float(np.abs(g - r).mean()) for g, r in zip(sides(got), sides(ref)))
        info.append(f'{c}: поля по бокам — разница с фоном ролика {ds:.2f} (≤ {TOL_SIDE})')
        if ds > TOL_SIDE: bad.append(f'[sides] {c}: поля по бокам — не фон ролика ({ds:.2f} > {TOL_SIDE}; рамка поверх?)'); keyed.add('sides')
        if dn <= TOL: bad.append(f'{c}: контроль не различим ({dn:.2f} ≤ {TOL}) — сверка слепая')
        if a.copy:
            Path(a.copy).mkdir(parents=True, exist_ok=True); got.save(Path(a.copy) / f'intro_{s["name"]}.png')
            Image.fromarray(ref).save(Path(a.copy) / f'intro_{s["name"]}_ffmpeg.png')
    # (2в) раскладка роликов: 4:3 без растяжки на своём месте
    if a.data:
        import struct
        pic = mx.picture(); st = pic[2] / (pic[3] * 4 / 3)
        if abs(st - 1) > .01: bad.append(f'[layout] картинка {pic[2]}x{pic[3]} растянута x{st:.3f}'); keyed.add('layout')
        for c in CLIPS:
            f = Path(a.data) / 'movies' / f'{c}.smv'
            if not f.exists(): bad.append(f'[layout] нет {f}'); keyed.add('layout'); continue
            x, w = struct.unpack_from('<HH', f.read_bytes()[:64], 40)
            if (x, w) != (pic[0], pic[2]):
                bad.append(f'[layout] {c}.smv: картинка x={x} w={w} (растяжка x{w / (pic[3] * 4 / 3):.3f}), нужно x={pic[0]} w={pic[2]} (выгрузить заново)'); keyed.add('layout')
        info.append(f'ролики: картинка {pic[2]}x{pic[3]} в ({pic[0]}, {pic[1]}), растяжка по ширине {st:.3f} (4:3 ±1 %)')
    # (3) START короче
    total = sum(mx.rmv_parse((mx.SRC / f'{c}.rmv').read_bytes(), c)['frames'] for c in CLIPS) / mx.FPS
    if not menu: bad.append('нет входа в меню (MENU)')
    else:
        t = float(menu[0]['t']); info.append(f'меню на {t:.1f} с (все ролики целиком {total:.1f} с)')
        if t >= total: bad.append(f'меню на {t:.1f} с не раньше {total:.1f} с — START не укоротил')
    # (4) куча
    if 'before' not in mem or 'after' not in mem: bad.append('нет INTROMEM before/after')
    else:
        du = int(mem['after']['used']) - int(mem['before']['used']); dm = int(mem['after']['maxblk']) - int(mem['before']['maxblk'])
        info.append(f'куча: used {du:+d} Б, наибольший блок {dm:+d} Б (допуск ±{MEM >> 10} КБ)')
        if abs(du) > MEM or abs(dm) > MEM: bad.append(f'куча после интро другая: used {du:+d}, блок {dm:+d}')
    if a.expect_fail:
        want = [k for k in a.expect_fail.split(',') if k]; miss = [k for k in want if k not in keyed]
        print(('intro: КРАСНЫЙ как надо — пойманы ' + ', '.join(want)) if not miss else 'intro: НЕ КРАСНЫЙ — не пойманы ' + ', '.join(miss))
        for b in bad: print('  - ' + b)
        return 0 if not miss else 1
    print(('intro: FAIL — ' + '; '.join(bad)) if bad else 'intro: PASS')
    for i in info: print('  ' + i)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
