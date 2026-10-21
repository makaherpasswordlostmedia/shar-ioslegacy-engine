#!/usr/bin/env python3
"""Прыжок Гомера в записи PS2: высота, время в воздухе, длина — по ВЕРНОМУ адресу мирового корня.

Мировой корень Гомера PS2 (L1) — sim::SimState 0xa24570 + 0x40 = 0xa245b0/b4/b8 (факт ps2-r6-foot-death,
native_binding). Старый 0xa24a70 (choreo::RootTransformController) в прыжке даёт ложные скачки — колонки legacy_*
печатаются только для сравнения.

  python3 -I tools/twins/homer_jump_ps2.py <trace.tsv> [<кадр от> <кадр до>] ...

trace.tsv — запись tools/twins/orig2.py с колонками rel, homer_x/y/z (0xa245b0..b8), legacy_x/y/z (0xa24a70..78).
Кадр rel = 1/50 с (PAL). Без диапазонов — каждый отрезок «в воздухе» (y выше земли первой строки).
С диапазоном — параболическая подгонка y(t) только по этим кадрам (для двойного прыжка: отдельно до и после второго X).
"""
import sys

FPS = 50.0


def load(p):
    L = open(p).read().splitlines()
    h = L[0].split('\t')
    rows = [dict(zip(h, l.split('\t'))) for l in L[1:] if l.strip()]
    out = []
    for d in rows:
        try:
            out.append((int(d['rel']), float(d['homer_x']), float(d['homer_y']), float(d['homer_z']),
                        float(d.get('legacy_x', 'nan')), float(d.get('legacy_y', 'nan')), float(d.get('legacy_z', 'nan'))))
        except (KeyError, ValueError):
            pass
    return out


def polyfit2(ts, ys):
    # наименьшие квадраты y = a t^2 + b t + c без numpy
    n = len(ts)
    s = [sum(t ** k for t in ts) for k in range(5)]
    r = [sum(y * t ** k for t, y in zip(ts, ys)) for k in range(3)]
    M = [[s[4], s[3], s[2], r[2]], [s[3], s[2], s[1], r[1]], [s[2], s[1], s[0], r[0]]]
    for i in range(3):
        piv = M[i][i]
        for j in range(i, 4):
            M[i][j] /= piv
        for k in range(3):
            if k != i:
                f = M[k][i]
                for j in range(i, 4):
                    M[k][j] -= f * M[i][j]
    a, b, c = M[0][3], M[1][3], M[2][3]
    res = max(abs(a * t * t + b * t + c - y) for t, y in zip(ts, ys)) if n else 0.0
    return a, b, c, res


def fit(rows, y0, f0, f1):
    sel = [r for r in rows if f0 <= r[0] <= f1]
    ts = [r[0] / FPS for r in sel]
    ys = [r[2] - y0 for r in sel]
    a, b, c, res = polyfit2(ts, ys)
    g = -2 * a
    tv = -b / (2 * a)
    apex = a * tv * tv + b * tv + c
    disc = b * b - 4 * a * c
    roots = sorted([(-b - disc ** .5) / (2 * a), (-b + disc ** .5) / (2 * a)]) if disc >= 0 else [float('nan')] * 2
    return dict(g=g, apex=apex, apex_frame=tv * FPS, ground_frames=[x * FPS for x in roots], resid=res,
                sampled_apex=max(ys) if ys else 0.0)


def segments(rows, y0, eps=1e-4):
    segs, s = [], None
    for i, r in enumerate(rows):
        air = r[2] > y0 + eps
        if air and s is None:
            s = i
        if not air and s is not None:
            segs.append((s, i - 1))
            s = None
    return segs


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    rows = load(argv[1])
    y0 = rows[0][2]
    print('запись %s: %d строк, земля y=%.4f' % (argv[1], len(rows), y0))
    for a, b in segments(rows, y0):
        ra, rb = rows[a], rows[b]
        before, after = rows[a - 1], rows[min(b + 1, len(rows) - 1)]
        k = max(range(a, b + 1), key=lambda i: rows[i][2])
        dxz = ((after[1] - before[1]) ** 2 + (after[3] - before[3]) ** 2) ** .5
        leg_dy = max(abs(rows[i][5] - rows[i][2]) for i in range(a, b + 1))
        leg_dxz = max(max(abs(rows[i][4] - rows[i][1]), abs(rows[i][6] - rows[i][3])) for i in range(a, b + 1))
        f = fit(rows, y0, ra[0], rb[0])
        print('в воздухе кадры %d..%d (земля %d и %d): выборочная вершина %.4f м на кадре %d; длина по земле %.3f м'
              % (ra[0], rb[0], before[0], after[0], rows[k][2] - y0, rows[k][0], dxz))
        print('  парабола: g=%.2f м/с², вершина %.4f м на кадре %.1f, отрыв/касание кадры %.2f / %.2f -> в воздухе %.3f с,'
              ' невязка до %.3f м' % (f['g'], f['apex'], f['apex_frame'], f['ground_frames'][0], f['ground_frames'][1],
                                     (f['ground_frames'][1] - f['ground_frames'][0]) / FPS, f['resid']))
        print('  старый адрес 0xa24a70: расхождение y до %.4f м, x/z до %.4f м' % (leg_dy, leg_dxz))
    rest = argv[2:]
    for i in range(0, len(rest) - 1, 2):
        f0, f1 = int(rest[i]), int(rest[i + 1])
        f = fit(rows, y0, f0, f1)
        print('подгонка кадров %d..%d: g=%.2f м/с², вершина %.4f м на кадре %.1f, пересечения земли %.2f / %.2f,'
              ' выборочная вершина %.4f, невязка до %.3f' % (f0, f1, f['g'], f['apex'], f['apex_frame'],
                                                            f['ground_frames'][0], f['ground_frames'][1],
                                                            f['sampled_apex'], f['resid']))
    for r in rows:
        if 16 <= r[0] <= 80:
            print('  %3d  y %.4f  legacy %.4f  x %.3f z %.3f' % (r[0], r[2] - y0, r[5] - y0, r[1], r[3]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
