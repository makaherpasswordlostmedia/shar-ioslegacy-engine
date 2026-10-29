#!/usr/bin/env python3
"""№405: замер пульса «Press START button» и неподвижности логотипа по записи PS2 (build/ps2ref/external/yt-bziOipI4gDI.mp4,
титульный на 11,0–19,3 с, 1280x720, 60 к/с). Жёлтая надпись: маска R,G > 120, B < 90 в полосе y 560–690; логотип: жёлтый знак
выше y 580. Синусоида по ширине надписи (перебор периода 0,4–0,9 с) -> период, меньшая/большая, центр; центр логотипа.
  python tests/title/ps2_pulse.py [--t0 11.75 --t1 19.2]   (нужен ffmpeg; кадры во временную папку)"""
import argparse, subprocess, tempfile, glob, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument('--t0', type=float, default=11.75); ap.add_argument('--t1', type=float, default=19.2)
a = ap.parse_args()
with tempfile.TemporaryDirectory() as d:
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(a.t0), '-i', str(ROOT / 'build/ps2ref/external/yt-bziOipI4gDI.mp4'),
                    '-t', str(a.t1 - a.t0), f'{d}/%05d.png'], check=True)
    t, w, cx, lc = [], [], [], []
    for i, f in enumerate(sorted(glob.glob(f'{d}/*.png'))):
        im = np.asarray(Image.open(f).convert('RGB')).astype(int)
        R = im[560:690]; m = (R[..., 0] > 120) & (R[..., 1] > 120) & (R[..., 2] < 90)
        L = im[:580]; lm = (L[..., 0] > 150) & (L[..., 1] > 130) & (L[..., 2] < 80)
        if m.sum() < 20 or lm.sum() < 20: continue
        xs = np.nonzero(m)[1]; t.append(a.t0 + i / 60.); w.append(xs.max() - xs.min() + 1); cx.append((xs.max() + xs.min()) / 2)
        lc.append(np.nonzero(lm)[1].mean())
t, w = np.array(t), np.array(w, float); best = None
for P in np.arange(.4, .9, .0005):
    X = np.c_[np.ones_like(t), np.sin(2 * np.pi * t / P), np.cos(2 * np.pi * t / P)]; c = np.linalg.lstsq(X, w, rcond=None)[0]
    r = ((X @ c - w) ** 2).mean()
    if best is None or r < best[0]: best = (r, P, c)
r, P, c = best; amp = np.hypot(c[1], c[2])
print(f'кадров {len(t)}; период {P:.3f} с; ширина {c[0] - amp:.1f}..{c[0] + amp:.1f} px записи, меньшая/большая {(c[0] - amp) / (c[0] + amp):.3f}; '
      f'остаток {r ** .5:.2f} px; центр надписи {min(cx):.1f}..{max(cx):.1f}; центр логотипа {min(lc):.2f}..{max(lc):.2f}')
