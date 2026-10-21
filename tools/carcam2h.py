#!/usr/bin/env python3
"""Камеры за машиной из моделей диска -> viewer/carcam.h (статическая таблица, ключ — имя машины, как в carparams.h).

    .venv/bin/python tools/carcam2h.py            # записать viewer/carcam.h
    .venv/bin/python tools/carcam2h.py --check    # сверить файл с диском (код выхода 1 — расходится)

Источник — диск Роба (только чтение): art/cars/*.p3d, чанк FollowCameraData 0x3000100 (I id; f rotation, elevation, magnitude,
target x y z — разбор hit-and-run-web/tools/p3d.py, MIT). У каждой машины два чанка: ближний (id < 256) и дальний
(id = ближний + 256). У оригинала в езде стоит ДАЛЬНИЙ: близнец v28_drive_cam (knowledge/facts/ps2-camera-fov.yaml) —
глаз 9,5–9,7 м позади начала модели famil_v, данные дальнего 10,25 · sin 1,23 = 9,66. elevation — угол от вертикали, рад;
magnitude — дистанция, м; цель — точка взгляда от начала модели (x вбок, y вверх, z вперёд), м. Машины без пары чанков или
с числами вне разумного (tt: elevation 42) в таблицу не идут — движок держит для них прежнюю камеру (CarParams camElev/camMag).
"""
import argparse, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read  # noqa: E402  (MIT)

CARS = ROOT / 'hit-and-run-web/source/game/art/cars'
OUT = ROOT / 'viewer/carcam.h'


def cams(p):
    """(near, far): кортежи (elev, mag, tx, ty, tz) или None"""
    cs = sorted(struct.unpack_from('<I6f', c.data) for c in read(p).children if c.id == 0x3000100)
    near = next((c for c in cs if c[0] < 256), None); far = next((c for c in cs if c[0] >= 256), None)
    ok = lambda c: c is not None and 0.2 <= c[2] <= 1.6 and 2.0 <= c[3] <= 20.0
    if not (ok(near) and ok(far)): return None
    return near[2:], far[2:]


def f(x):
    s = f'{x:.4f}'.rstrip('0').rstrip('.')
    return (s if '.' in s else s + '.') + 'f'


def render():
    rows = []
    for p in sorted(CARS.glob('*.p3d')):
        c = cams(p)
        if not c or len(p.stem) > 11: continue
        (ne, nm, *_), (fe, fm, tx, ty, tz) = c
        rows.append(f'  {{"{p.stem}", {f(ne)}, {f(nm)}, {f(fe)}, {f(fm)}, {f(tx)}, {f(ty)}, {f(tz)}}},')
    L = ['// Камеры за машиной из моделей диска: FollowCameraData (чанк 0x3000100) art/cars/*.p3d.',
         '// СГЕНЕРИРОВАНО tools/carcam2h.py — руками не править (проверка: tools/carcam2h.py --check).',
         '// Два варианта на машину: ближний (id < 256) и дальний (id + 256); у оригинала в езде — дальний (близнец v28_drive_cam,',
         '// knowledge/facts/ps2-camera-fov.yaml). elev — угол от вертикали, рад; mag — дистанция, м; цель t* — точка взгляда от',
         '// начала модели (x вбок, y вверх, z вперёд), м. Подключается только в main.c (chaseCamUpdate).',
         '#ifndef SHAR_CARCAM_H', '#define SHAR_CARCAM_H',
         'typedef struct { char name[12]; float nearElev, nearMag, farElev, farMag, tx, ty, tz; } CarCamData;',
         'static const CarCamData carCamTab[] = {', *rows, '};',
         '#define CAR_CAMS ((int)(sizeof carCamTab / sizeof carCamTab[0]))', '#endif', '']
    return '\n'.join(L), len(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    text, n = render()
    if a.check:
        cur = Path(a.out).read_text() if Path(a.out).exists() else ''
        print(f'carcam2h: {"совпадает с диском" if cur == text else "РАСХОДИТСЯ с диском"} ({n} машин)')
        return 0 if cur == text else 1
    Path(a.out).write_text(text); print(f'carcam2h: {n} машин -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
