#!/usr/bin/env python3
"""№877 (Роб 23.10 утро: «пропекай на все уровни и получай максимальный прок от ночных тестов»): таблица дали из бота-репортёра.
Бот (tools/scout/scout.c) снял каждую точку земли через 10 м в 8 сторон на двух высотах глаза и посчитал, сколько экрана занимает
город дальше 140 и 200 м. За 115 м PVS нет — движок рисует всё в пирамиде, даже то, что закрыто домами. Таблица говорит движку,
в какую сторону из какого места даль 250 м вообще видна; где не видна — город рисуется до 150 или 200 м (туман, лента горизонта,
подгрузка клеток остаются прежними).

  python3 tools/scout/dal877.py LEVEL.shr SCOUT.csv OUT.bin [--th 0.0025]

Запас: доля экрана за порогом ≤ th (1 %, правило отчёта бота); узел сетки — точка бота (шаг 10,5 м), движок берёт худшее из 4 узлов
вокруг глаза и из ближайшей стороны с двумя соседними (угол кадра шире стороны бота). Нет точки в каком-то из 4 узлов — даль не ограничивается.
OUT.bin: 'DAL1', u32 подпись таблицы кусков (viewer/pvs2.h pvs2Sig), f32 x0, z0, шаг, u32 W, H;
         W·H × u16 (2 бита на сторону 0..7: 0 — 150 м, 1 — 200, 2 — 250, 3 — нет данных), W·H × i16 верх глаза бота (дм)."""
import csv, struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opq863 import table_sig



def main():
    lv, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    th = float(sys.argv[sys.argv.index('--th') + 1]) if '--th' in sys.argv else .01
    b = Path(lv).read_bytes(); npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76)
    rows = [r for r in csv.DictReader(open(src)) if r.get('pieces_d250') not in (None, '')]
    A = {k: np.array([float(r[k]) for r in rows]) for k in ('x', 'y', 'z', 'eye', 'dir', 'px200', 'px250')}
    tot = 128 * 72
    code = np.where((A['px200'] + A['px250']) / tot <= th, 0, np.where(A['px250'] / tot <= th, 1, 2)).astype(np.int8)
    ux = np.unique(np.round(A['x'], 2)); STEP = float(np.median(np.diff(ux)))   # шаг точек бота (tools/scout/dump.py --step 10 -> 7 клеток высот по 1,5 м)
    x0, z0 = A['x'].min(), A['z'].min()
    gx = np.round((A['x'] - x0) / STEP).astype(int); gz = np.round((A['z'] - z0) / STEP).astype(int); d = A['dir'].astype(int)
    assert np.abs(gx * STEP + x0 - A['x']).max() < .05 and np.abs(gz * STEP + z0 - A['z']).max() < .05, 'точки бота не на решётке'
    W, H = gx.max() + 1, gz.max() + 1
    need = np.full((H, W, 8), -1, np.int8); ytop = np.full((H, W), -32768, np.int32)
    eyeh = np.where(A['eye'] == 0, 2.0, 3.2)
    np.maximum.at(need, (gz, gx, d), code)
    np.maximum.at(ytop, (gz, gx), np.round((A['y'] + eyeh) * 10).astype(np.int32))
    pk = np.zeros((H, W), np.uint16)
    for k in range(8):
        v = need[:, :, k].astype(np.int16); v[v < 0] = 3
        pk |= (v.astype(np.uint16) << (2 * k))
    sig = table_sig(b, npc, ptab)
    Path(out).write_bytes(b'DAL1' + struct.pack('<I3f2I', sig, x0, z0, STEP, W, H) + pk.tobytes() + np.clip(ytop, -32768, 32767).astype('<i2').tobytes())
    # оценка выигрыша по ракурсам бота: решение клетки с запасом (3 стороны) против прежних 250 м
    T = {k: np.array([float(r[k]) for r in rows]) for k in ('tris_fp90_d150', 'tris_fp90_d200', 'tris_fp90_d250')}
    Np = np.pad(need, ((0, 1), (0, 1), (0, 0)), constant_values=3)
    n3 = np.max([Np[gz + a, gx + c, (d + e) % 8] for a in (0, 1) for c in (0, 1) for e in (-1, 0, 1)], axis=0)   # как движок: глаз между узлами
    t = np.select([n3 == 0, n3 == 1], [T['tris_fp90_d150'], T['tris_fp90_d200']], T['tris_fp90_d250'])
    base = T['tris_fp90_d250']
    print(f'{lv}: ракурсов {len(rows)}: узлов {W}x{H} шаг {STEP:.1f} м: 150 м {100 * (n3 == 0).mean():.0f}%, 200 м {100 * (n3 == 1).mean():.0f}%, 250 м {100 * (n3 == 2).mean():.0f}%;'
          f' треугольников города (оценка) медиана {np.median(base) / 1e3:.1f}k -> {np.median(t) / 1e3:.1f}k, 95% {np.percentile(base, 95) / 1e3:.1f}k -> {np.percentile(t, 95) / 1e3:.1f}k'
          f' -> {out} ({Path(out).stat().st_size} Б, подпись {sig:08x})')


if __name__ == '__main__':
    main()
