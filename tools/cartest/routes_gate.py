#!/usr/bin/env python3
"""Сверка гейта пункта 12 (tools/cartest/routes_gate.sh) с routes.txt. Из smoke.txt движка: строка "RAMP i/n имя x y z курс"
— куда ↑ / ↓ поставили машину (сразу после carPlace), строка "SHOT имя t pos x y z курс" — где машина стоит в момент
снимка, через 2 с (viewer/smoke.h, smokePose).

  python3 tools/cartest/routes_gate.py OUTDIR ROUTES.txt [--still]

Обход (по умолчанию), ПРОВАЛ если: строки RAMP не 1/n 2/n 3/n 2/n или не те имена (в том числе лишние после ↑ пешком
и в полёте: снимки foot и fly, машина там же, где на r2back, 0.3 м); постановка не на старт маршрута
(xz > 0.5 м, высота > 1 м, курс > 2°) или нос не на кромку (> 10°, кромка из build/sandbox/routes-l1.tsv, если до неё
5 м и больше); на снимках r0..r3 не четыре разные точки (попарно < 5 м); нет жёлтой строки HUD внизу слева на r1..r2back
или она есть на r0 до нажатий. ЗАМЕЧАНИЕ (не провал): машина поставлена верно, но к снимку не удержалась на старте
(xz > 1.5 м или высота > 3 м) — это данные маршрута (пункты 9 и 11), не обход.
--still (без routes.txt рядом с EBOOT): ПРОВАЛ, если машина на любом снимке не на месте r0 (0.5 м, 3°), есть строки RAMP
или жёлтая строка. Выход 0 = PASS, 1 = FAIL; первая строка — вердикт."""
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOUR = [('r1', 0), ('r2', 1), ('r3', 2), ('r2back', 1)]


def routes(p):
    out = []
    if not Path(p).exists():
        return out
    for l in Path(p).read_text().splitlines():
        f = l.split()
        if len(f) >= 6 and not l.startswith('#'):
            out.append(dict(name=f[0], x=float(f[1]), y=float(f[2]), z=float(f[3]), h=float(f[4])))
    return out


def adiff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def label_px(png):
    """жёлтые пиксели строки трамплина (HUD, ряд 32: y 256..264 кадра 480x272, x 0..360); кадр внизу окна"""
    from PIL import Image   # нет Pillow — гейт падает, а не молча пропускает проверку строки
    if not png.exists():
        return -1
    im = Image.open(png).convert('RGB'); w, h = im.size; s = w / 480.0; top = h - 272 * s
    box = im.crop((0, int(top + 255 * s), int(360 * s), int(top + 265 * s)))
    return sum(1 for r, g, b in box.getdata() if r > 225 and g > 225 and b < 120)


def main(out, rt, still):
    out = Path(out); R = routes(rt)
    lips = {}
    tsv = ROOT / 'build/sandbox/routes-l1.tsv'
    if tsv.exists():
        for l in tsv.read_text().splitlines():
            f = l.split('\t')
            if len(f) >= 4:
                lx, _, lz = map(float, f[3].split()); lips[f[0]] = (lx, lz)
    log = (out / 'smoke.txt').read_text().splitlines() if (out / 'smoke.txt').exists() else []
    pos, ramp = {}, []
    for l in log:
        p = l.split()
        if len(p) >= 8 and p[0] == 'SHOT' and p[3] == 'pos':
            pos[p[1]] = tuple(map(float, p[4:8]))
        elif len(p) >= 7 and p[0] == 'RAMP':
            ramp.append((p[1], p[2], tuple(map(float, p[3:7]))))
    ended = any(l.startswith('END') for l in log)
    names = ['r0'] + [n for n, _ in TOUR] + ['foot', 'fly']
    fails, warns = [], []
    if not ended:
        fails.append('нет END (движок упал или завис)')
    miss = [n for n in names if n not in pos]
    if miss:
        fails.append('нет позиции машины в SHOT: ' + ' '.join(miss))
    px = {n: label_px(out / f'{n}.png') for n in names}
    rows = []
    if not miss:
        x0, y0, z0, h0 = pos['r0']
        for n in names:
            x, y, z, h = pos[n]
            rows.append(f"{n:7} {x:9.2f} {y:7.2f} {z:9.2f} {math.degrees(h):7.1f}°  от r0 {math.hypot(x - x0, z - z0):6.1f} м  строка {px[n]} px")
    if still and not miss:
        for n in names[1:]:
            x, y, z, h = pos[n]
            if math.hypot(x - x0, z - z0) > 0.5 or adiff(h, h0) > math.radians(3):
                fails.append(f'{n}: машина сдвинулась без routes.txt ({math.hypot(x - x0, z - z0):.1f} м)')
        if ramp:
            fails.append('строки RAMP без routes.txt: ' + ' '.join(r[0] for r in ramp))
        lit = [n for n in names if px[n] > 150]
        if lit:
            fails.append('жёлтая строка без routes.txt: ' + ' '.join(lit))
    elif not still:
        if len(R) < 3:
            fails.append(f'в routes.txt {len(R)} трамплинов, нужно 3 и больше')
        want = [f'{i + 1}/{len(R)}' for _, i in TOUR]
        if [r[0] for r in ramp] != want:
            fails.append(f"строки RAMP {' '.join(r[0] for r in ramp) or 'нет'} вместо {' '.join(want)}")
        for (n, i), (idx, nm, (x, y, z, h)) in zip(TOUR, ramp):   # постановка — сразу после carPlace
            if i >= len(R):
                continue
            r = R[i]; d = math.hypot(x - r['x'], z - r['z'])
            if nm != r['name']:
                fails.append(f"{n}: RAMP {idx} {nm} вместо {r['name']}")
            if d > 0.5 or abs(y - r['y']) > 1.0 or adiff(h, r['h']) > math.radians(2):
                fails.append(f"{n}: поставлена не на старт {r['name']} (xz {d:.2f} м, y {y - r['y']:+.2f} м, курс {math.degrees(h - r['h']):+.1f}°)")
            lp = lips.get(r['name'])
            if lp and math.hypot(lp[0] - x, lp[1] - z) >= 5.0 and adiff(h, math.atan2(lp[0] - x, lp[1] - z)) > math.radians(10):
                fails.append(f"{n}: нос не на кромку {r['name']}")
            if n in pos:                                          # к снимку, через 2 с
                sx, sy, sz, _ = pos[n]; ds = math.hypot(sx - r['x'], sz - r['z'])
                if ds > 1.5 or abs(sy - r['y']) > 3.0:
                    warns.append(f"{n}: {r['name']} поставлена верно, но не удержалась на старте (к снимку {ds:.1f} м вбок, "
                                 f"{sy - r['y']:+.1f} м по высоте)")
        if not miss:
            p4 = [pos[n] for n in ('r0', 'r1', 'r2', 'r3')]
            near = [f'r{a}/r{b}' for a in range(4) for b in range(a + 1, 4) if math.hypot(p4[a][0] - p4[b][0], p4[a][2] - p4[b][2]) < 5.0]
            if near:
                fails.append('на снимках не четыре разные точки: ' + ' '.join(near))
            for n in ('foot', 'fly'):                             # ↑ пешком и в полёте — прежнее поведение, машина стоит
                if n in pos and math.hypot(pos[n][0] - pos['r2back'][0], pos[n][2] - pos['r2back'][2]) > 0.3:
                    fails.append(f'{n}: ↑ сдвинул машину ({math.hypot(pos[n][0] - pos["r2back"][0], pos[n][2] - pos["r2back"][2]):.1f} м)')
            if px['r0'] > 150:
                fails.append(f"жёлтая строка на r0 до нажатий ({px['r0']} px)")
            dark = [n for n, _ in TOUR if px[n] < 400]
            if dark:
                fails.append('нет строки трамплина на снимке: ' + ' '.join(dark))
    verdict = 'routes_gate: ' + ('PASS' if not fails else 'FAIL: ' + '; '.join(fails)) + (' (--still)' if still else ' (обход)')
    text = (verdict + '\n' + ''.join('ЗАМЕЧАНИЕ ' + w + '\n' for w in warns) + '\n'.join(rows) + '\nRAMP: ' +
            (' '.join(f'{a} {b} {c[0]:.2f} {c[1]:.2f} {c[2]:.2f} {math.degrees(c[3]):.1f}°' for a, b, c in ramp) or 'нет') + '\n')
    (out / 'gate.txt').write_text(text)
    print(text, end='')
    return 0 if not fails else 1


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) != 2:
        sys.exit(__doc__)
    sys.exit(main(a[0], a[1], '--still' in sys.argv))
