#!/usr/bin/env python3
"""Облёт камерой перед заездом мини-игры (правка Роба 420): art/missions/generic/minigamecam.p3d (грузит scripts/ss.mfk —
LoadP3DFile("art\\missions\\generic\\minigamecam.p3d")) -> bonus/flyby.cam для viewer/bonus_play.h.

В данных: анимация камеры CAM_minigamecamShape (тип CAM, 120 кадров, 30 кадров/с; каналы TRAN 70 ключей, LOOK 25, UP 12, FOV 1,05 рад,
NCLP 0,01, FCLP 1000) и камера minigamecamShape; путь — от решётки старта (car1..car4 у всех трасс b01..b07 в одной точке, ~(−4; 0; 32,5))
вверх и назад. Кадры снимаются как у перелётов гостиной (tools/frontend3d_export.py camera: линейно между ключами, z отзеркален,
как уровни порта).

Формат BFC1 (little endian): 'BFC1', u32 кадров, f32 кадров/с, u32 0; дальше на кадр 12 f32: позиция xyz, взгляд xyz (единичный),
верх xyz (единичный), fov (рад, горизонталь 4:3 — как прочие камеры данных), near, far (как в данных; near движок поднимает до своего).
    python tools/bonus/flyby_export.py [--out build/bonus/flyby.cam]
    python tools/bonus/flyby_export.py --dump      # кадры 0, 30, 60, 90, 119 (гейт сверяет с ними журнал движка)
Читает только диск и hit-and-run-web/tools (MIT)."""
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import frontend3d_export as F  # noqa: E402
from p3d import read  # noqa: E402

SRC = ROOT / 'hit-and-run-web/source/game/art/missions/generic/minigamecam.p3d'
SCRIPT = ROOT / 'hit-and-run-web/source/game/scripts/ss.mfk'
OUT = ROOT / 'build/bonus/flyby.cam'
ANIM = 'CAM_minigamecamShape'


def frames():
    """-> (кадров, кадров/с, массив [n, 12])"""
    assert 'minigamecam.p3d' in SCRIPT.read_text(errors='replace'), 'ss.mfk не грузит minigamecam.p3d'
    A = F.anims(read(SRC))
    typ, nfr, fps, groups = A[ANIM]
    assert typ == 'CAM', typ
    ch = groups[ANIM]
    rows = []
    for f in range(nfr):
        pos = F.sample(*ch['TRAN'], f); look = F.sample(*ch['LOOK'], f); up = F.sample(*ch['UP'], f)
        look = look / np.linalg.norm(look); up = up / np.linalg.norm(up)
        fov = F.sample(*ch['FOV'], f)[0]; nc = F.sample(*ch['NCLP'], f)[0]; fc = F.sample(*ch['FCLP'], f)[0]
        m = np.array([1, 1, -1])
        rows.append(np.r_[pos * m, look * m, up * m, fov, nc, fc])
    return nfr, float(fps), np.array(rows)


def write(out):
    n, fps, rows = frames()
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(struct.pack('<4sIfI', b'BFC1', n, fps, 0) + rows.astype('<f4').tobytes())
    print('flyby.cam: %d кадров, %.0f к/с, %.2f с, %d Б; старт (%.2f, %.2f, %.2f) -> конец (%.2f, %.2f, %.2f)' % (
        n, fps, (n - 1) / fps, out.stat().st_size, *rows[0, :3], *rows[-1, :3]))


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--dump' in a:
        n, fps, rows = frames()
        for f in (0, 30, 60, 90, n - 1):
            print('%d %.3f %.3f %.3f' % (f, *rows[f, :3]))
        sys.exit(0)
    write(a[a.index('--out') + 1] if '--out' in a else OUT)
