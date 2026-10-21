#!/usr/bin/env python3
"""Шкала Hit & Run оригинала по записи прохождения PS2 (правка Роба 112, 30.09: «сверяйся с оригиналом напрямую»).

    python tools/ps2ref/hnr_track.py [--video build/ps2ref/external/yt-bziOipI4gDI.mp4] [--fps 10] [--from S] [--to S]
                                     [--out build/ps2ref/hnr/track.csv] [--sheet T0 T1]

HUD записи (1280x720, 60 к/с): радар — круг внизу справа, центр (952, 568); по ободу — тёмная дорожка шкалы (радиус ~75 px),
наверху мигалки (синяя и красная). Шкала Hit & Run — жёлтый указатель, который едет по дорожке по часовой стрелке от верхней
точки. Кадр за кадром: радар виден (зелёный диск внутри), угол жёлтого указателя (градусы от 12 часов по часовой) и число жёлтых
точек на дорожке. Выход — CSV: t, radar, tip, yellow. Дальше по графику: прибавки (скачки вверх), спад (наклон), полная шкала.
--sheet T0 T1: лист вырезок радара с подписью угла (проверка глазом)."""
import argparse, math, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CX, CY = 952.5, 567.5          # центр радара в кадре 1280x720 (сверено по кадру 2:41)
R0, R1 = 66.0, 84.0            # кольцо дорожки шкалы
BOX = 100                      # полуразмер вырезки вокруг центра
W, H = 2 * BOX, 2 * BOX


def frames(video, fps, t0, t1):
    x0, y0 = int(CX - BOX), int(CY - BOX)
    cmd = ['ffmpeg', '-loglevel', 'error', '-ss', str(t0)] + (['-to', str(t1)] if t1 else []) + [
        '-i', str(video), '-vf', f'fps={fps},crop={W}:{H}:{x0}:{y0}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3; k = 0
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        yield t0 + k / fps, np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.int16); k += 1
    p.wait()


# маски кольца и диска (в координатах вырезки)
yy, xx = np.mgrid[0:H, 0:W]
dx, dy = xx - BOX + (CX - int(CX)), yy - BOX + (CY - int(CY))
RR = np.hypot(dx, dy)
ANG = (np.degrees(np.arctan2(dx, -dy)) + 360.0) % 360.0      # 0 — 12 часов, по часовой
RING = (RR >= R0) & (RR <= R1)
DISK = RR <= 45.0


def measure(a):
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    green = (G > 120) & (G > R + 25) & (G > B + 25)
    radar = green[DISK].mean() > 0.35
    yel = (R > 185) & (G > 160) & (B < 110) & (R - B > 110) & RING
    n = int(yel.sum())
    tip = float(ANG[yel].max()) if n >= 4 else -1.0
    # жёлтое, начинающееся у 12 часов, может «перейти» через 0 — берём наибольший угол, не считая узкой полосы у 359..360
    return radar, tip, n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video', type=Path, default=ROOT / 'build/ps2ref/external/yt-bziOipI4gDI.mp4')
    ap.add_argument('--fps', type=float, default=10.0)
    ap.add_argument('--from', dest='t0', type=float, default=0.0)
    ap.add_argument('--to', dest='t1', type=float, default=0.0)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/ps2ref/hnr/track.csv')
    ap.add_argument('--sheet', type=float, nargs=2)
    a = ap.parse_args()
    if a.sheet:
        from PIL import Image, ImageDraw
        tiles = []
        for t, fr in frames(a.video, 2.0, a.sheet[0], a.sheet[1]):
            radar, tip, n = measure(fr)
            im = Image.fromarray(fr.astype(np.uint8)); d = ImageDraw.Draw(im)
            d.text((4, 2), f'{int(t // 60)}:{t % 60:04.1f} {"R" if radar else "-"} {tip:.0f}° {n}', fill=(255, 0, 255))
            if tip >= 0:
                r = (R0 + R1) / 2; x = BOX + r * math.sin(math.radians(tip)); y = BOX - r * math.cos(math.radians(tip))
                d.ellipse((x - 4, y - 4, x + 4, y + 4), outline=(255, 0, 255))
            tiles.append(im)
        cols = 8; rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * W, rows * H))
        for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * W, (i // cols) * H))
        out = a.out.with_name(f'sheet_{int(a.sheet[0])}_{int(a.sheet[1])}.png'); out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out); print('лист', out, len(tiles)); return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, 'w') as f:
        f.write('t,radar,tip,yellow\n'); n = 0
        for t, fr in frames(a.video, a.fps, a.t0, a.t1):
            radar, tip, k = measure(fr); f.write(f'{t:.2f},{int(radar)},{tip:.1f},{k}\n'); n += 1
    print(f'кадров {n} -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
