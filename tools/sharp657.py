#!/usr/bin/env python3
"""№657: мера резкости и «прыжка мипа» по кадрам (снимки смоука или кадры видео с PSP).
  tools/sharp657.py PREFIX N [DIR]     — файлы DIR/PREFIX_0.png .. PREFIX_{N-1}.png подряд (кадр за кадром)
  tools/sharp657.py --video FILE.MOV T0 T1 [fps] — кадры видео от T0 до T1 секунд (нужен ffmpeg), область дороги/земли внизу по центру
Резкость = дисперсия лапласиана серого в окне земли (низ центр); прыжок = наибольшее |Δ резкости| между соседними кадрами к средней, %.
На железе целый треугольник прыгает между мипами: прыжок заметно больше 1-2 %, как в эмуляторе (там плавно)."""
import sys, subprocess, tempfile, glob, os
import numpy as np
from PIL import Image
def sharp(img, roi):
    g = np.array(img.convert("L"), dtype=float)
    h, w = g.shape; y0, y1, x0, x1 = [int(v) for v in (roi[0]*h, roi[1]*h, roi[2]*w, roi[3]*w)]
    g = g[y0:y1, x0:x1]
    l = g[1:-1, 1:-1]*4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return l.var()
def report(name, v):
    d = [abs(v[i+1]-v[i]) for i in range(len(v)-1)]
    print(f"{name:10s} кадров {len(v):3d} резкость средняя {np.mean(v):8.1f}  мин {min(v):8.1f}  макс {max(v):8.1f}  прыжок макс {max(d):7.1f} ({100*max(d)/np.mean(v):.1f}%)")
ROI = (0.52, 0.86, 0.22, 0.88)   # низ кадра, центр: земля/дорога
if sys.argv[1] == "--video":
    f, t0, t1 = sys.argv[2], sys.argv[3], sys.argv[4]; fps = sys.argv[5] if len(sys.argv) > 5 else "30"
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-v", "error", "-ss", t0, "-to", t1, "-i", f, "-vf", f"fps={fps}", os.path.join(td, "f%04d.png")], check=True)
        fs = sorted(glob.glob(os.path.join(td, "f*.png"))); report("video", [sharp(Image.open(x), ROI) for x in fs])
else:
    pre, n = sys.argv[1], int(sys.argv[2]); d = sys.argv[3] if len(sys.argv) > 3 else "."
    report(pre, [sharp(Image.open(f"{d}/{pre}_{i}.png"), ROI) for i in range(n)])
