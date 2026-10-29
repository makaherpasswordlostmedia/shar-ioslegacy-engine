#!/usr/bin/env python3
"""Правка Роба 248 (03.10, видео IMG_7707 1:50: «пончик (вывеска Lard Lad) всё равно бьётся»; раньше 88: «пончик битый — внутри
битые треугольники»). Причина по кадрам и эмулятору: дальше LOD_DIST = 50 м (viewer/main.c drawPiece) кусок города рисовался
дальней версией — у статуи Lard Lad (меш common_gens82Shape_020, char_swatches_m, l1z2) в ней оставалось 92 треугольника из
1209 (статуя пропадала, в воздухе висел пончик), у пончика (common_gens82Shape_006, Lard_Donut_m) — 40 из 100 (кольцо с
дырами, «ромб» внутри). С 570ac3a (правки 224/237/251) у кусков города дальних версий нет (флаг 2048 F_NEAR — ближняя на
любой дальности); этот гейт держит, что так и осталось: что движок рисует дальше 50 м, покрывает ту же площадь, что вблизи.

Проверки (уровень SHR7, только чтение):
  1. Lard Lad: куски города в коробке статуи (x 238..257, y 2..30, z 338..359 в осях движка) с верхом выше 15 м — статуя и
     пончик; их площадь дальше 50 м / площадь вблизи >= 0.95 у каждого, и таких кусков не меньше двух.
  2. Весь город: кусков, у которых дальше 50 м остаётся меньше половины площади (при площади вблизи от 2 м²), — ноль.
Запуск: .venv/bin/python tests/lod/far_full.py build/level.shr   (код 0 — PASS, 1 — FAIL)
Красный контроль — уровень до 570ac3a: build/seams/ref/level_pre_seams.shr (tests/lod/far_full.sh гоняет оба)."""
import struct, sys
from pathlib import Path
import numpy as np

F_NOIDX, F_V12, F_NEAR, F_SKY = 16, 32, 2048, 4
LARD_BOX = ((238.0, 2.0, 338.0), (257.0, 30.0, 359.0)); LARD_TOP = 15.0
RATIO_LARD, RATIO_CITY, MIN_AREA = 0.95, 0.5, 2.0


def area(b, base, fl, cnt, sc, o):
    if cnt <= 0: return 0.0
    vs = 12 if fl & F_V12 else 16
    raw = np.frombuffer(b, np.uint8, cnt * vs, base).reshape(cnt, vs)
    xyz = (raw[:, 6:12] if vs == 12 else raw[:, 8:14]).copy().view('<i2').reshape(cnt, 3).astype(np.float64) * (sc / 32768.0) + o
    T = xyz[:cnt // 3 * 3].reshape(-1, 3, 3)
    return float(np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1).sum() / 2)


def pieces(path):
    b = Path(path).read_bytes(); assert b[:4] == b'SHR7', f'{path}: не SHR7'
    npc, = struct.unpack_from('<I', b, 8); ptab, = struct.unpack_from('<I', b, 76)
    ncell, ctab = struct.unpack_from('<II', b, 80)
    cells = [struct.unpack_from('<6fIIIII', b, ctab + 48 * i) for i in range(ncell)]
    out = []
    for i in range(npc):
        r = struct.unpack_from('<6fiIIII3ffIII2I', b, ptab + 80 * i)
        bb, fl, ni, own = r[0:6], r[7], r[9], r[10]; o = np.array(r[11:14]); sc = r[14]; off, nf, ci = r[15:18]
        if own != 0 or fl & F_SKY or not fl & F_NOIDX: continue          # город (не машина, не небо), формат без индексов
        vs = 12 if fl & F_V12 else 16; base = cells[ci][9] + off
        near = area(b, base, fl, ni, sc, o)
        far = near if fl & F_NEAR else area(b, base + ni * vs, fl, nf, sc, o)   # как drawPiece: F_NEAR — ближняя на любой дальности
        out.append(dict(i=i, bb=bb, fl=fl, ni=ni, nf=0 if fl & F_NEAR else nf, near=near, far=far))
    return out


def main(path):
    P = pieces(path); fails = 0
    (x0, y0, z0), (x1, y1, z1) = LARD_BOX
    lard = [p for p in P if p['bb'][0] >= x0 and p['bb'][1] >= y0 and p['bb'][2] >= z0 and p['bb'][3] <= x1 and p['bb'][4] <= y1
            and p['bb'][5] <= z1 and p['bb'][4] >= LARD_TOP]
    print(f'far_full: {path} — кусков города {len(P)}, с флагом F_NEAR {sum(1 for p in P if p["fl"] & F_NEAR)}')
    for p in lard:
        r = p['far'] / p['near'] if p['near'] else 0.0
        print(f'   Lard Lad: кусок {p["i"]} верх {p["bb"][4]:.1f} м: треугольников вблизи {p["ni"] // 3}, дальше 50 м {p["nf"] // 3 if not p["fl"] & F_NEAR else p["ni"] // 3}'
              f'{" (F_NEAR)" if p["fl"] & F_NEAR else ""}; площадь {p["near"]:.1f} -> {p["far"]:.1f} м² ({r:.2f})')
    bad_lard = [p for p in lard if not p['near'] or p['far'] / p['near'] < RATIO_LARD]
    ok1 = len(lard) >= 2 and not bad_lard; fails += not ok1
    print(f'{"ok  " if ok1 else "FAIL"} 1. статуя и пончик Lard Lad дальше 50 м целиком (>= {RATIO_LARD}): кусков {len(lard)}, неполных {len(bad_lard)}')
    lost = [p for p in P if p['near'] >= MIN_AREA and p['far'] / p['near'] < RATIO_CITY]
    tn, tf = sum(p['near'] for p in P), sum(p['far'] for p in P)
    ok2 = not lost; fails += not ok2
    print(f'{"ok  " if ok2 else "FAIL"} 2. кусков города, теряющих дальше 50 м больше половины площади: {len(lost)} '
          f'(площадь города дальше 50 м {tf / max(tn, 1e-9):.3f} от ближней)')
    for p in sorted(lost, key=lambda p: p['far'] / p['near'])[:5]:
        print(f'   кусок {p["i"]}: {p["near"]:.1f} -> {p["far"]:.1f} м², коробка {tuple(round(v, 1) for v in p["bb"])}')
    print(f'far_full: {"PASS" if not fails else "FAIL"}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'build/level.shr'))
