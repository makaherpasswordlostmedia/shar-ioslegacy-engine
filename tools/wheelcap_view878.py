#!/usr/bin/env python3
"""№878: вид боковины колеса w0 (диск-накладка) так, как она лежит на колесе: растеризация треугольников боковины с картинкой, вид сбоку.
  python3 tools/wheelcap_view878.py OUT.png [машина ...]   (без списка — все машины art/cars)"""
import json, os, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wheelspin878 as W   # noqa: E402
from convert import Converter, GAME, OUT   # noqa: E402
S_ = 128


def cap_view(meta, raw, wheel='w0'):
    m2 = dict(meta); m2['objects'] = [o for o in meta['objects'] if o['name'] == wheel]
    cs = W.caps(m2, raw)
    if not cs: return None
    allP = np.concatenate([T.reshape(-1, 3) for _, T, _ in cs]); side = np.median(allP[:, 0])
    sel = [(u, T[T[:, :, 0].mean(1) >= side], U[T[:, :, 0].mean(1) >= side]) for u, T, U in cs]   # одна сторона колеса (наружная)
    sel = [e for e in sel if len(e[1])]
    if not sel: return None
    allP = np.concatenate([T.reshape(-1, 3) for _, T, _ in sel])
    cy, cz = (allP[:, 1].max() + allP[:, 1].min()) / 2, (allP[:, 2].max() + allP[:, 2].min()) / 2
    R = max(np.abs(allP[:, 1] - cy).max(), np.abs(allP[:, 2] - cz).max()) + 1e-6
    img = np.zeros((S_, S_, 3)); dep = np.full((S_, S_), -1e9)
    yy, xx = np.mgrid[0:S_, 0:S_]; px_ = np.stack([xx + .5, yy + .5], -1).reshape(-1, 2)
    for url, T, U in sel:
        im = W.tex_img(url); H, Wd = im.shape[:2]
        for t, u in zip(T, U):
            P2 = np.c_[(t[:, 2] - cz) / R * (S_ / 2 - 2) + S_ / 2, S_ / 2 - (t[:, 1] - cy) / R * (S_ / 2 - 2)]
            a, b, c = P2; M = np.array([b - a, c - a]).T
            if abs(np.linalg.det(M)) < 1e-9: continue
            lo = np.floor(P2.min(0)).astype(int).clip(0, S_ - 1); hi = np.ceil(P2.max(0)).astype(int).clip(0, S_ - 1)
            sub = np.stack(np.mgrid[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1][::-1], -1).reshape(-1, 2) + .5
            l12 = np.linalg.solve(M, (sub - a).T).T; l0 = 1 - l12.sum(1); ok = (l12 >= -1e-6).all(1) & (l0 >= -1e-6)
            if not ok.any(): continue
            bc = np.c_[l0, l12][ok]; q = bc @ u; d = bc @ t[:, 0]
            x = (np.mod(q[:, 0], 1) * Wd).astype(int).clip(0, Wd - 1); y = (np.mod(q[:, 1], 1) * H).astype(int).clip(0, H - 1)
            sp = (sub[ok] - .5).astype(int); front = d > dep[sp[:, 1], sp[:, 0]]
            img[sp[front, 1], sp[front, 0]] = im[y[front], x[front], :3]; dep[sp[front, 1], sp[front, 0]] = d[front]
    return Image.fromarray((img * 255).astype(np.uint8))


def main():
    out = Path(sys.argv[1]); names = sys.argv[2:] or sorted(p.stem for p in (GAME / 'art' / 'cars').glob('*.p3d'))
    conv = Converter(); tiles = []
    for nm in names:
        tmp = f'wcv_{os.getpid()}'
        try:
            conv.export(GAME / 'art' / 'cars' / f'{nm}.p3d', tmp, vehicle=True)
            meta = json.loads((OUT / f'{tmp}.json').read_text()); raw = (OUT / f'{tmp}.bin').read_bytes()
        except Exception: continue
        finally:
            for e in ('json', 'bin'):
                if (OUT / f'{tmp}.{e}').exists(): (OUT / f'{tmp}.{e}').unlink()
        v = cap_view(meta, raw)
        if v: tiles.append((nm, v))
    cols = 10; S = Image.new('RGB', (cols * 130, ((len(tiles) + cols - 1) // cols) * 146), (40, 40, 40)); d = ImageDraw.Draw(S)
    for i, (nm, v) in enumerate(tiles):
        x, y = (i % cols) * 130, (i // cols) * 146; S.paste(v, (x + 1, y + 16)); d.text((x + 2, y + 2), nm, fill=(230, 230, 230))
    S.save(out); print(out, len(tiles))


if __name__ == '__main__':
    main()
