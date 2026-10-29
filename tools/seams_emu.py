#!/usr/bin/env python3
"""Правка Роба 106 «стыки рябят, проступают швы»: непокрытые пиксели дальних видов по снимкам эмулятора.

Прогон: SMOKE_SCN=tools/seams_scenario.txt SMOKE_FLAGS=clearchk SMOKE_OPTS=2017f tools/smoke.sh DIR
  clearchk (viewer/main.c) — кадр чистится пурпурным; opts 2017f — без неба и HUD (O_SKY, O_HUD сняты): всё, что не закрыл
  город, остаётся пурпурным. В игре (небо последним, цвет кадра не чистится) такой пиксель — фон или прошлый кадр сквозь стык.
  2013f — то же без дальних версий кусков (ALLNEAR: ближняя версия везде) — эталон «город без упрощения».

  python tools/seams_emu.py RUN                     -> по снимкам RUN/v*.png: пурпур всего и «швы» (пурпур в тонких полосах)
  python tools/seams_emu.py RUN --ref REF [--tol T]  -> сравнение с эталоном REF (тот же уровень без дальних версий): швы RUN
                                                        против швов REF × (1 + T) + 30 на вид — ТОЛЬКО СВОДКА, код всегда 0
  python tools/seams_emu.py --plant SRC.shr DST.shr  -> заведомо плохой вход: копия уровня, у которой каждый треугольник
                                                        дальних версий ужат к центру на 3 % — щели по всем рёбрам дальше 50 м

НЕ ГЕЙТ (30.09, правка 106): посадка --plant (щели по всем 120 тыс. дальних треугольников) дала швов 1748 против 1604 у
уровня и 1544 у эталона — порог не пробит. PPSSPP рисует в 4× и в плавающей точке, за щелью в городе почти всегда есть
геометрия (земля под бордюром) — пурпура нет; к тому же снимки на загруженном Маке запаздывают на вид (v10/v11 — кадр v09).
Щели дальних версий меряет геометрия: tools/seams_far.py --vs.

Шов — пурпурный пиксель, у которого пурпурная полоса по вертикали или по горизонтали не длиннее THIN пикселей PSP:
тонкая щель между поверхностями (бордюр, край тротуара). Небо без неба — большие пурпурные области, в счёт швов не идёт.
Снимок окна PPSSPP может быть увеличен (масштаб — по ширине 480): полосы и счёт переводятся в пиксели PSP."""
import argparse, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image

THIN = 2   # пикселей PSP: полоса пурпура не толще — шов


def runs(m, axis):
    """длина пурпурной полосы, в которой лежит пиксель, вдоль оси axis (0 — по столбцу, 1 — по строке)"""
    a = m if axis == 1 else m.T
    h, w = a.shape
    out = np.zeros(a.shape, np.int32)
    pad = np.zeros((h, 1), bool)
    d = np.diff(np.concatenate([pad, a, pad], 1).astype(np.int8), axis=1)
    for y in range(h):
        st = np.nonzero(d[y] == 1)[0]; en = np.nonzero(d[y] == -1)[0]
        for s, e in zip(st, en): out[y, s:e] = e - s
    return out if axis == 1 else out.T


def count(png):
    im = np.asarray(Image.open(png).convert('RGB')).astype(np.int16)
    s = im.shape[1] / 480.0                                         # масштаб окна к кадру PSP
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    m = (r >= 190) & (b >= 190) & (g <= 70) & (np.abs(r - b) <= 40)
    thin = m & ((runs(m, 0) <= THIN * s + .5) | (runs(m, 1) <= THIN * s + .5))
    return m.sum() / (s * s), thin.sum() / (s * s)


def table(d):
    shots = sorted(p for p in Path(d).glob('v*.png'))
    if not shots: sys.exit(f'seams_emu: нет снимков v*.png в {d}')
    return {p.stem: count(p) for p in shots}


def plant(src, dst, k=.97):
    """копия уровня: треугольники дальних версий кусков города ужаты к своему центру (int16 вершин, SHR7 без индексов)"""
    b = bytearray(Path(src).read_bytes()); assert b[:4] == b'SHR7', 'не SHR7'
    ntex, npc = struct.unpack_from('<II', b, 4); ptab, = struct.unpack_from('<I', b, 76); ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    n = 0
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        fl, nv, ni, own = r[7:11]; off, nf, ci = r[15:18]
        if own != 0 or not fl & 16 or nf < 3: continue
        vs = 12 if fl & 32 else 16; o = 6 if vs == 12 else 8
        base = cells[ci][9] + off + ni * vs
        a = np.frombuffer(bytes(b[base:base + nf * vs]), np.uint8).reshape(nf, vs).copy()
        xyz = a[:, o:o + 6].copy().view('<i2').reshape(-1, 3, 3).astype(np.float64)
        xyz = xyz.mean(1, keepdims=True) + (xyz - xyz.mean(1, keepdims=True)) * k
        a[:, o:o + 6] = np.round(xyz).clip(-32767, 32767).astype('<i2').reshape(nf, 3).view(np.uint8)
        b[base:base + nf * vs] = a.tobytes(); n += nf // 3
    Path(dst).write_bytes(bytes(b))
    print(f'посажено: {n:,} треугольников дальних версий ужаты на {100 * (1 - k):.0f} % -> {dst}')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--plant': plant(sys.argv[2], sys.argv[3]); return 0
    ap = argparse.ArgumentParser()
    ap.add_argument('run'); ap.add_argument('--ref'); ap.add_argument('--tol', type=float, default=.25)
    a = ap.parse_args()
    t = table(a.run)
    ref = table(a.ref) if a.ref else {}
    print(f'{"вид":5} {"пурпур":>8} {"швы":>7}' + (f' {"эталон швы":>11}' if ref else ''))
    for k, (tot, th) in t.items():
        print(f'{k:5} {tot:8.0f} {th:7.0f}' + (f' {ref[k][1]:11.0f}' if k in ref else ''))
    sth = sum(v[1] for v in t.values())
    print(f'итого: швы {sth:.0f} пикс. PSP на {len(t)} видов ({a.run})')
    if not ref: return 0
    rth = sum(ref[k][1] for k in t if k in ref)
    lim = rth * (1 + a.tol) + 30 * len(t)
    ok = sth <= lim
    print(f'{"в пределе" if ok else "СВЕРХ предела"}: швы {sth:.0f} {"<=" if ok else ">"} предел {lim:.0f} '
          f'(эталон без дальних версий {rth:.0f} × {1 + a.tol:.2f} + 30 × {len(t)})')
    return 0   # сводка, не гейт (см. шапку): посадка --plant порог не пробивает


if __name__ == '__main__':
    sys.exit(main())
