#!/usr/bin/env python3
"""№878 (Роб 23.10 после TEST50): «важно учитывать свет и блик, чтобы тени не крутились по колесу. Если диск хромированный (с переливом) —
статичный, не крутится. Если диск без перелива — крутится». С №867 боковины колеса (картинка диска) не крутятся у всех машин.
Бот проходит все машины диска (art/cars/*.p3d), берёт боковины колёс w0..w3 (треугольники вдоль оси колеса, как viewer/wheelcap.h) и
читает их картинку в точках боковины. Перелив = запечённый свет: яркость зависит от высоты точки на колесе (сверху блик, снизу тень),
а не от угла вокруг оси. Мера: по кругу на каждом радиусе — однобокий перепад (1–2 гармоники) против рисунка (спицы, болты: 3 и выше). Перелив есть — диск неподвижен (как сейчас); нет — диск крутится вместе с колесом.

  python3 tools/wheelspin878.py OUT_DIR    -> OUT_DIR/wheelspin878.txt (имена машин с крутящимися дисками), wheelspin878.tsv (мера по машинам),
                                              wheelspin878.png (лист: диск каждой машины и решение)
"""
import json, os, re, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import psp_export as pe   # noqa: E402
from convert import Converter, GAME, OUT   # noqa: E402

R2_MIN, GRAD_MIN = .5, .08   # перелив: однобокий перепад — не меньше половины изменений яркости по кругу и размах ≥ 8 % шкалы


def tex_img(url):
    img = Image.open(pe.ASSETS / url).convert('RGBA')
    if url in pe.PNG_SRC and os.environ.get('SHR_PNG_FLIP', '1') != '0': img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return np.asarray(img, np.float32) / 255.


def caps(meta, raw):
    """-> [(url, P (n,3,3) в осях колеса, UV (n,3,2))] боковин всех колёс"""
    out = []
    for obj in meta['objects']:
        if not re.fullmatch(r'w[0-3]', obj['name']): continue
        for prim in meta['meshes'].get(obj['mesh'], []):
            at = prim['attributes']
            g = lambda k, w: np.frombuffer(raw, '<f4', at[k][1], at[k][0]).reshape(-1, w)
            pos, uv = g('position', 3), g('uv', 2); idx = np.frombuffer(raw, '<u4', at['indices'][1], at['indices'][0])
            T = pos[idx].reshape(-1, 3, 3); U = uv[idx].reshape(-1, 3, 2)
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); l2 = (n * n).sum(1)
            m = (l2 > 0) & (n[:, 0] ** 2 >= .49 * l2)
            url = meta['materials'].get(prim['shader'], {}).get('textureUrl', '')
            if m.any() and url: out.append((url, T[m], U[m]))
    return out


def measure(cs):
    """Яркость боковины по кругу: на каждом кольце (радиус) профиль по углу 24 сектора без среднего кольца; гармоники 1–2 — однобокий
    перепад (блик/тень запечены в картинке), 3 и выше — рисунок диска (спицы, болты). shine — доля гармоник 1–2, amp — их размах."""
    Y, Z, L, A = [], [], [], []
    W = np.array([(a, b, 1 - a - b) for a in np.linspace(0, 1, 9) for b in np.linspace(0, 1, 9) if a + b <= 1])
    for url, T, U in cs:
        im = tex_img(url); H, Wd = im.shape[:2]
        for t, u in zip(T, U):
            p = W @ t; q = W @ u
            x = (np.mod(q[:, 0], 1) * Wd).astype(int).clip(0, Wd - 1); y = (np.mod(q[:, 1], 1) * H).astype(int).clip(0, H - 1)
            px = im[y, x]
            Y += list(p[:, 1]); Z += list(p[:, 2]); L += list(px[:, :3] @ np.array([.299, .587, .114])); A += list(px[:, 3])
    Y, Z, L, A = map(np.array, (Y, Z, L, A))
    k = A > .5
    if k.sum() < 60: return None
    Y, Z, L = Y[k], Z[k], L[k]
    cy, cz = (Y.max() + Y.min()) / 2, (Z.max() + Z.min()) / 2; Y, Z = Y - cy, Z - cz
    r = np.hypot(Y, Z); R = r.max() + 1e-6; th = np.arctan2(Y, Z)
    rb = np.minimum((r / R * 5).astype(int), 4); ab = ((th + np.pi) / (2 * np.pi) * 24).astype(int) % 24
    p12 = pp = 0.; amp = 0.; wsum = 0.
    for ring in range(5):
        m = rb == ring
        if m.sum() < 48: continue
        prof = np.full(24, np.nan)
        for j in range(24):
            mm = m & (ab == j)
            if mm.any(): prof[j] = L[mm].mean()
        if np.isnan(prof).sum() > 4: continue
        idx = np.arange(24); good = ~np.isnan(prof); prof = np.interp(idx, idx[good], prof[good], period=24)
        F = np.fft.rfft(prof - prof.mean()) / 24; P = np.abs(F) ** 2
        w = m.sum(); p12 += w * (P[1] + P[2]); pp += w * P[3:].sum(); amp += w * 2 * np.sqrt(P[1] + P[2]); wsum += w
    if wsum == 0: return None
    return dict(r2=float(p12 / max(p12 + pp, 1e-9)), grad=float(amp / wsum), lum=float(L.mean()), std=float(L.std()), n=int(k.sum()))


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    conv = Converter(); rows = []; spin = []; tiles = []
    for p in sorted((GAME / 'art' / 'cars').glob('*.p3d')):
        name = p.stem; tmp = f'ws878_{os.getpid()}'
        try:
            conv.export(p, tmp, vehicle=True)
            meta = json.loads((OUT / f'{tmp}.json').read_text()); raw = (OUT / f'{tmp}.bin').read_bytes()
        except Exception as e:
            rows.append(f'{name}\t-\t-\t-\tнет модели ({type(e).__name__})'); continue
        finally:
            for ext in ('json', 'bin'):
                if (OUT / f'{tmp}.{ext}').exists(): (OUT / f'{tmp}.{ext}').unlink()
        cs = caps(meta, raw)
        m = measure(cs) if cs else None
        if not m: rows.append(f'{name}\t-\t-\t-\tнет боковин с картинкой'); continue
        shine = m['r2'] >= R2_MIN and m['grad'] >= GRAD_MIN
        if not shine: spin.append(name)
        rows.append(f"{name}\t{m['r2']:.2f}\t{m['grad']:.2f}\t{m['std']:.2f}\t{'перелив — стоит' if shine else 'без перелива — крутится'}")
        url, T, U = cs[0]; im = tex_img(url); H, Wd = im.shape[:2]
        uv = np.concatenate([u_.reshape(-1, 2) for url_, _, u_ in cs if url_ == url]); lo = np.mod(uv, 1).min(0); hi = np.mod(uv, 1).max(0)
        x0, y0, x1, y1 = int(lo[0] * Wd), int(lo[1] * H), max(int(hi[0] * Wd), int(lo[0] * Wd) + 2), max(int(hi[1] * H), int(lo[1] * H) + 2)
        crop = Image.fromarray((im[y0:y1, x0:x1, :3] * 255).astype(np.uint8)).resize((96, 96), Image.NEAREST)
        tiles.append((name, crop, shine, m))
    (out / 'wheelspin878.txt').write_text('# №878 машины, у которых диск колеса без перелива — крутится вместе с колесом (tools/wheelspin878.py)\n' + '\n'.join(spin) + '\n')
    (out / 'wheelspin878.tsv').write_text('# машина\tR2\tперепад\tразброс\tрешение\n' + '\n'.join(rows) + '\n')
    cols = 10; S = Image.new('RGB', (cols * 100, ((len(tiles) + cols - 1) // cols) * 124), (20, 20, 20)); d = ImageDraw.Draw(S)
    for i, (nm, im_, sh, m) in enumerate(tiles):
        x, y = (i % cols) * 100, (i // cols) * 124
        S.paste(im_, (x + 2, y + 14)); d.text((x + 2, y + 1), nm[:14], fill=(230, 230, 230))
        d.text((x + 2, y + 111), ('стоит' if sh else 'крутится') + f" {m['r2']:.2f}", fill=(240, 200, 80) if sh else (120, 220, 120))
    S.save(out / 'wheelspin878.png')
    print(f'машин {len(rows)}, диск крутится у {len(spin)}: ' + ' '.join(spin))


if __name__ == '__main__':
    main()
