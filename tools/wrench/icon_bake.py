#!/usr/bin/env python3
"""Значки-спрайты (добавка Роба 18.10: «!» над персонажами миссий и трубка над будкой — тем же способом, что монета и ключ): кадры настоящей
3D-модели значка из msnart.shr (выгрузка tools/wrench/msnart_sprite_dump.py) для tools/coin/coin_pack.py; растеризатор — wrench_raster.py, без света
(значки msnart рисуются без освещения: цвет вершин × картинка).
    python3 tools/wrench/icon_bake.py DUMP_DIR OUT_DIR spin [N=32] [RES=128]     — «!»: модель в осях сустава, оборот вокруг вертикали через центр рамки
    python3 tools/wrench/icon_bake.py DUMP_DIR OUT_DIR anim:F [N=32] [RES=128]   — трубка: N поз клипа на один оборот (F кадров клипа на оборот), вид спереди
Центр кадра — центр рамки вершин меша после позы (тот же, что msnart.c передаёт в iconSprHook); печатает HALF для coin_pack.py --half."""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wrench_raster import raster   # noqa: E402

def main(src, out, mode, N=32, RES=128):
    src, out = Path(src), Path(out); out.mkdir(parents=True, exist_ok=True)
    d = json.loads((src / 'coin.json').read_text()); info = json.loads((src / 'info.json').read_text())
    P = np.array(d['P'], np.float64); UV = np.array(d['UV'], np.float64); UV[:, 1] = 1.0 - UV[:, 1]; C = np.array(d['C'], np.float64)[:, :3]
    T = np.array(d['T'], np.int64); TX = d['TX']; CUT = d['CUT']
    texs = [np.asarray(Image.open(src / f'coin_tex{"" if i == 0 else i}.png').convert('RGBA'), np.float64) / 255.0 for i in range(d['ntex'])]
    c0 = (P.min(0) + P.max(0)) / 2
    if mode == 'spin':
        X = P - c0; views = []
        for k in range(N):
            a = 2 * math.pi * k / N; ca, sa = math.cos(a), math.sin(a)
            views.append(np.c_[X[:, 0] * ca + X[:, 2] * sa, X[:, 1], -X[:, 0] * sa + X[:, 2] * ca])
    else:
        F = int(mode.split(':')[1]); JF = info['mesh_joint_frames']; views = []
        for k in range(N):
            J = np.array(JF[int(round(k * F / N)) % len(JF)], np.float64); R = np.c_[J[0:3], J[3:6], J[6:9]]
            views.append((P - c0) @ R.T)   # поворот сустава вокруг центра рамки (сдвиг кадра снят: центр даёт игра)
    S = 1.08 * 2 * max(float(np.abs(V[:, :2]).max()) for V in views)
    for k, V in enumerate(views): raster(V, UV, C, T, texs, TX, S, RES, lit_on=False, cut=CUT).save(out / f'f_{k:02d}.png')
    print('ICONBAKE', info['name'], mode, N, 'кадров', RES, 'px; HALF', round(S / 2, 4), 'центр меша', [round(float(x), 4) for x in c0])

if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 32, int(a[4]) if len(a) > 4 else 128)
