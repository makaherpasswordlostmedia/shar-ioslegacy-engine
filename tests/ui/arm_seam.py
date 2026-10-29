#!/usr/bin/env python3
"""Гейт правки Роба 319 (04.10: «у правой металлической руки, держащей карточку брифинга, явный шов-разрыв»).
Брифинг (MissionLoad.pag) собирается экспортёром tools/ui_export.py как в пакет; руки (звенья cliparm.png) рисуются на чёрном
по местам и порядку пакета; по средней строке трубы ищется столбец заметно темнее соседей (шов). Зелёный — шва нет ни у одной
руки; красный контроль UI_TILE_SEAM_OLD=1 (каждое звено отдельно, как до правки) обязан упасть: столбец x 471 правой руки.
    .venv/bin/python tests/ui/arm_seam.py            # новый код + красный контроль
"""
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U  # noqa: E402


def seams(old):
    if old: os.environ['UI_TILE_SEAM_OLD'] = '1'
    else: os.environ.pop('UI_TILE_SEAM_OLD', None)
    items, icons = U.build_items('missionload')
    A = U.Assets()
    dl, _ = U.adapt(items, icons, 'psp', A, U.FontCache('psp'))
    out = []
    for side in ('Left', 'Right'):
        arms = [t for t in dl if t['type'] == U.T_IMG and t['name'].startswith('clipArm' + side)]
        if not arms: out.append((side, None, 'нет руки')); continue
        cv = np.zeros((272, 640, 4), np.float32)   # запас 80 px за правым краем
        x0 = min(t['dst'][0] for t in arms); x1 = max(t['dst'][0] + t['dst'][2] for t in arms)
        y0 = arms[0]['dst'][1]
        for t in arms:                              # порядок пакета, «над» по альфе
            bm = np.asarray(A.bitmaps[t['bitmaps'][0]].convert('RGBA')).astype(np.float32) / 255
            x, y = t['dst'][0] + 80, t['dst'][1]; h, w = bm.shape[:2]
            reg = cv[y:y + h, x:x + w]; a = bm[..., 3:4]
            reg[..., :3] = bm[..., :3] * a + reg[..., :3] * (1 - a); reg[..., 3:] = a + reg[..., 3:] * (1 - a)
        lum = cv[..., :3].mean(-1)
        # строка трубы: самая светлая строка руки (блик посередине трубы)
        band = lum[y0:y0 + arms[0]['dst'][3], x0 + 80:x1 + 80]
        r = int(band.mean(1).argmax())
        row = band[max(0, r - 1):r + 2].mean(0)
        # внутренность трубы (без концов полосы по 2 px): столбец темнее 0,7 медианы соседей ±3 — шов
        bad = []
        for i in range(2, len(row) - 2):
            nb = np.median(np.r_[row[max(0, i - 3):i], row[i + 1:i + 4]])
            if nb > 0.15 and row[i] < 0.7 * nb:
                bad.append((x0 + i, round(float(row[i]) * 255), round(float(nb) * 255)))
        out.append((side, bad, ''))
    return out


def main():
    fails = []
    new, old = seams(False), seams(True)
    for side, bad, note in new:
        print(f'  новый код, рука {side}: ' + (note or ('швов нет' if not bad else f'ШОВ {bad}')))
        if note or bad: fails.append(f'рука {side}: {note or bad}')
    caught = [b for _, b, _ in old if b]
    for side, bad, note in old:
        print(f'  красный контроль UI_TILE_SEAM_OLD=1, рука {side}: ' + (note or ('швов нет' if not bad else f'шов {bad}')))
    if not caught: fails.append('красный контроль не поймал шов (гейт слепой)')
    print('FAIL: ' + '; '.join(fails) if fails else 'PASS: руки брифинга без шва, красный контроль пойман')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
