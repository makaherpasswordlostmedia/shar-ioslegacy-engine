#!/usr/bin/env python3
"""Ключ-спрайт (№803, Роб 18.10: «гаечный ключ тоже перевести в спрайт, как монету: кадры 3D-модели, запечённые в Blender»): выгрузка настоящей
3D-модели ключа с диска (art/wrench.p3d, меш wrench7Shape, картинка wrench.bmp) для запекания тем же tools/coin/coin_blender.py.
    python3 tools/wrench/wrench_dump.py OUT_DIR  ->  OUT_DIR/coin.json (P, UV, C, T — как у coin_dump.py), OUT_DIR/coin_tex.png
Имена файлов — как у монеты: coin_blender.py читает именно их. Данные диска — только чтение; выход — в build/ (ассеты не коммитить)."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HRW = ROOT / 'hit-and-run-web'
if not HRW.exists(): HRW = Path.home() / 'Downloads' / 'shar-psp' / 'hit-and-run-web'
sys.path.insert(0, str(HRW / 'tools'))
import p3d, textures   # noqa: E402
import convert   # noqa: E402

def main(outd):
    outd = Path(outd); outd.mkdir(parents=True, exist_ok=True)
    root = p3d.read(HRW / 'source' / 'game' / 'art' / 'wrench.p3d')
    mesh = next(c for c in p3d.walk(root) if c.id == 0x10000 and p3d.string(c.data)[0] == 'wrench7Shape')
    P, UV, C, T = [], [], [], []
    for pg in mesh.children:
        if pg.id != 0x10002: continue
        _, parts = convert.geometry(pg)
        for part in parts:
            base = len(P); pos = part['position']; pos[:, 2] *= -1   # convert.geometry отзеркалил z под Three.js — вернуть оси игры
            uv = part['uv']; P += pos.tolist(); UV += [[float(u), 1.0 - float(v)] for u, v in uv]   # у p3d v от верха картинки; coin_blender.py сам переворачивает v (как у монеты из level.shr)
            col = part.get('color'); C += ([[float(r), float(g), float(b), 1.0] for r, g, b in col] if col is not None else [[1.0, 1.0, 1.0, 1.0]] * len(pos))
            tri = part['indices'].reshape(-1, 3)[:, [0, 2, 1]] + base   # и порядок обхода обратно
            T += tri.tolist()
    for c in root.children:
        if c.id != 0x19000 or not re.search(rb'wrench\.bmp', c.data): continue
        for k in p3d.walk(c):
            if k.id == 0x19002:
                i = k.data.find(b'P3DI'); r = textures.decode_image(k.data[i:])
                (r[0] if isinstance(r, tuple) else r).convert('RGBA').save(outd / 'coin_tex.png')
    (outd / 'coin.json').write_text(json.dumps({'P': P, 'UV': UV, 'C': C, 'T': T}))
    xs, ys, zs = zip(*P)
    print('ключ: %d вершин, %d треуг.; рамка x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f -> %s' % (len(P), len(T), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), outd))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'build' / 'wrench_src')
