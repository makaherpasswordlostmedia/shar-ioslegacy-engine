#!/usr/bin/env python3
"""Гейт своего увеличителя слабых картинок интерфейса (Роб 28.09, правка 22; tools/ui_export.py resample / _upscale_hq).
Что меряется — на тех картинках диска, которые на экране PSP больше себя: пузырь задания (helptext 3-срезом до размера
рамки HUD), значок задания (msnicons: marage, kwike, simpsons) в аватаре, значок q*.png. Для каждой:
  резкость — средняя крутизна краёв (|градиент| яркости x альфа по 5% самых сильных краёв, на пиксель экрана PSP) не ниже
             UPSCALE_MIN_GAIN от той же меры простого Ланцоша (прежний путь) — края снова резкие на пикселе PSP;
  без ореолов — ни один канал не выходит за мин/макс своих 2x2 исходных соседей больше чем на 1/255 (анти-звон);
  цвет/альфа — средние по картинке совпадают с простым Ланцошем в пределах 4/255 (не темнее, не светлее).
Отрицательный контроль: UI_UPSCALE_PLAIN=1 (прежний простой Ланцош) обязан покраснеть по резкости.
    tests/ui/upscale_check.py            -> PASS/FAIL (код 0/1)
    tests/ui/upscale_check.py --negative -> PASS, если простой Ланцош покраснел
    tests/ui/upscale_check.py --show OUT.png   лист было/стало x4"""
import os
os.environ.setdefault('BUBBLE_AA_OLD', '1')   # №515: пузырь helptext теперь собирается по профилям (pill_aa), у него свой гейт tests/ui/bubble_aa.py; здесь проверяется сам увеличитель на 3-срезе
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSCALE_MIN_GAIN = 1.04


def main():
    if '--negative' in sys.argv:
        env = dict(os.environ, UI_UPSCALE_PLAIN='1')
        r = subprocess.run([sys.executable, __file__], env=env, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print('PASS (отрицательный контроль: простой Ланцош покраснел)'); return 0
        print('FAIL (отрицательный контроль прошёл — замер резкости ничего не ловит)'); return 1
    sys.path.insert(0, str(ROOT / 'tools'))
    import numpy as np
    import ui_export as U
    from PIL import Image
    imgs = U.all_images()
    cases = []
    items, icons = U.build_items('hud')
    out, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
    box = next(t for t in out if t['name'] == 'MessageBox')
    cases.append(('пузырь helptext -> %dx%d' % tuple(box['dst'][2:]), imgs['helptext.png'], box['dst'][2], box['dst'][3], 'hslice'))
    ic = next(t for t in out if t['name'] == 'ObjectiveIcon')
    fw, fh = ic.get('extframe', [0, 0, 0, 0])[2:] or (0, 0)
    G = U.WEB / 'source/game/art/frontend/dynaload/images/msnicons'
    for n in ('char/marage', 'location/kwike', 'location/simpsons'):
        for c in U.read(G / (n + '.p3d')).children:
            if c.id == 0x19005 and fw and fh:
                _, im = U.decode_sprite_image(c); cases.append(('значок %s -> %dx%d' % (n, fw, fh), im, fw, fh, 'plain'))
    q = ic['slots'][0]; qn = sorted(k for k in imgs if k.startswith('q') and k[1:-4].isalpha())[0]
    cases.append(('значок %s -> %dx%d' % (qn, q[1][2], q[1][3]), imgs[qn], q[1][2], q[1][3], 'plain'))

    def lum_a(a):
        return (a[..., :3] @ np.array([.299, .587, .114], np.float32)) * a[..., 3]   # яркость поверх чёрного

    def sharp(a):
        L = lum_a(a); gx = np.abs(np.diff(L, axis=1)); gy = np.abs(np.diff(L, axis=0))
        g = np.concatenate([gx.ravel(), gy.ravel()]); n = max(1, len(g) // 20)
        return float(np.sort(g)[-n:].mean())
    bad = 0; sheet = []
    for name, src, w, h, how in cases:
        if not U.upscales(src.size, (w, h)) and how != 'hslice':
            print('ok    %-40s не увеличивается (%dx%d -> %dx%d)' % (name, src.width, src.height, w, h)); continue
        f = (lambda im, W, H: U.hslice(im, W, H)) if how == 'hslice' else (lambda im, W, H: U.resample(im, W, H))
        got = np.asarray(f(src, w, h)).astype(np.float32) / 255
        if how == 'hslice':   # точная ступенька: те же куски 3-среза, но «ближайший»
            ref = np.asarray(hslice_nearest(U, src, w, h)).astype(np.float32) / 255
        else:
            ref = np.asarray(src.resize((w, h), Image.NEAREST)).astype(np.float32) / 255
        was = os.environ.get('UI_UPSCALE_PLAIN'); os.environ['UI_UPSCALE_PLAIN'] = '1'
        plain = np.asarray(f(src, w, h)).astype(np.float32) / 255
        if was is None:
            os.environ.pop('UI_UPSCALE_PLAIN', None)
        s, s0, sp = sharp(got), sharp(ref), sharp(plain)
        gain = s / sp if sp > 0 else 0
        dmean = float(np.abs(got.reshape(-1, 4).mean(0) - plain.reshape(-1, 4).mean(0)).max() * 255)
        halo = 0.0
        if how != 'hslice':   # анти-звон: за мин/макс 2x2 исходных соседей (премульт.)
            a = np.asarray(src.convert('RGBA')).astype(np.float32) / 255; pm = a.copy(); pm[..., :3] *= pm[..., 3:4]
            sh_, sw_ = pm.shape[:2]; kx, ky = w / sw_, h / sh_
            fx = (np.arange(w) + .5) / kx - .5; fy = (np.arange(h) + .5) / ky - .5
            x0 = np.clip(np.floor(fx).astype(int), 0, sw_ - 1); x1 = np.clip(x0 + 1, 0, sw_ - 1)
            y0 = np.clip(np.floor(fy).astype(int), 0, sh_ - 1); y1 = np.clip(y0 + 1, 0, sh_ - 1)
            q = np.stack([pm[y0][:, x0], pm[y0][:, x1], pm[y1][:, x0], pm[y1][:, x1]])
            g2 = got.copy(); g2[..., :3] *= g2[..., 3:4]
            halo = float(max((g2 - q.max(0)).max(), (q.min(0) - g2).max(), 0) * 255)
        ok = gain >= UPSCALE_MIN_GAIN and dmean <= 4.0 and halo <= 1.5
        bad += not ok
        print('%-5s %-40s резкость x%.3f от простого Ланцоша (>= %.2f; «ближайший» %.2f, Ланцош %.2f); ореол %.1f/255; средние %+.2f/255' % (
            'ok' if ok else 'FAIL', name, gain, UPSCALE_MIN_GAIN, s / s0 if s0 else 0, sp / s0 if s0 else 0, halo, dmean))
        sheet.append((plain, got))
    print('увеличитель: %s' % ('OK' if not bad else 'FAIL %d' % bad))
    if '--show' in sys.argv and sheet:
        W = max(p.shape[1] for p, _ in sheet) * 2 + 8; H = sum(p.shape[0] for p, _ in sheet) + 4 * len(sheet)
        canvas = Image.new('RGBA', (W, H), (60, 110, 60, 255)); y = 0
        for p, g in sheet:
            for i, a in enumerate((p, g)):
                canvas.alpha_composite(Image.fromarray((a * 255 + .5).astype(np.uint8), 'RGBA'), (i * (W // 2), y))
            y += p.shape[0] + 4
        canvas.resize((W * 4, H * 4), Image.NEAREST).save(sys.argv[sys.argv.index('--show') + 1])
    return 1 if bad else 0


def hslice_nearest(U, img, W, H):
    from PIL import Image
    iw, ih = img.size
    cap = max(1, min(iw // 2 - 1, ih // 2)); capW = max(1, int(round(cap * H / ih)))
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.paste(img.crop((0, 0, cap, ih)).resize((capW, H), Image.NEAREST), (0, 0))
    out.paste(img.crop((iw - cap, 0, iw, ih)).resize((capW, H), Image.NEAREST), (W - capW, 0))
    if W - 2 * capW > 0:
        out.paste(img.crop((cap, 0, iw - cap, ih)).resize((W - 2 * capW, H), Image.NEAREST), (capW, 0))
    return out


if __name__ == '__main__':
    sys.exit(main())
