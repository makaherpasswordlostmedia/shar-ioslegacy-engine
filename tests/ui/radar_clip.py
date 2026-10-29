#!/usr/bin/env python3
"""Круг радара (Роб 27.09: «карта была в круге, он пропал и криво нанесён»): замер на точных кадрах GE тестового EBOOT.

    python tests/ui/radar_clip.py --shr build/ui.shr --out build/ui_shots/radar_after
    python tests/ui/radar_clip.py --shr build/ui_shots/radar_before/ui.shr --out build/ui_shots/radar_neg   # красное

Тестовый EBOOT (tests/ui) на ровном сером фоне снимает радар в точках из radar.txt: «empty» далеко за картой (карта
прозрачна, эталон всего остального HUD), центр у спавна и четыре дороги, ближайшие к углам карты уровня (там же край
текстуры карты). Разность кадра с «empty» = только пиксели карты. Проверки (ожидание из данных ui.shr и l1hudmap):
  1 карта: ни одного пикселя карты дальше внутреннего края кольца шкалы + 1 px; внутри круга карта есть (иначе
    пустая карта прошла бы проверку)
  2 круг: рамка шкалы нарисована: >= 80% её непрозрачных пикселей отличаются от фона
  3 конус обзора: в секторе конуса дальше края круга + 1.5 px нет пикселей, кроме рамки и мигалки
  4 мигалка над радаром видна всегда (Роб 27.09: «мигалка была, пропала»)
Код 0 все зелёные, 1 красное, 2 сломан замер (нет снимков, эмулятор занят).
"""
import argparse
import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
W, H = 480, 272
BG = (200, 200, 200)

ap = argparse.ArgumentParser()
ap.add_argument('--shr', type=Path, default=ROOT / 'build/ui.shr')
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--eboot', type=Path, default=ROOT / 'tests/ui/build/EBOOT.PBP')
args = ap.parse_args()


def die(msg):
    print('radar_clip: замер сломан: ' + msg)
    sys.exit(2)


# ---- ui.shr: элементы HUD, слоты, текстуры --------------------------------------------------------------
b = args.shr.read_bytes()
hdr = struct.unpack_from('<4sI18I', b, 0)
ntex, otex, nitem, oitem, nscreen, oscreen = hdr[2:8]
nslot, oslot = hdr[16], hdr[17]
layout = json.loads((ROOT / 'build/ui/layout.json').read_text())['screens']['hud']
first = struct.unpack_from('<4I', b, oscreen)[0]


def item(i):
    r = b[oitem + (first + i) * 64: oitem + (first + i + 1) * 64]
    typ, tag = r[0], r[2]
    sf, sn = struct.unpack_from('<HH', r, 28)
    px, py, ang = struct.unpack_from('<3f', r, 32)
    clip = struct.unpack_from('<f', r, 48)[0]
    return dict(type=typ, tag=tag, first=sf, count=sn, px=px, py=py, ang=ang, clip=clip)


texcache = {}


def tex_rgba(ti):
    if ti in texcache:
        return texcache[ti]
    psm, flags, w, h, op, oc, nc, bw, rows, _ = struct.unpack_from('<4H6I', b, otex + ti * 32)
    rb = bw if psm == 5 else bw // 2
    raw = np.frombuffer(b, np.uint8, count=rb * rows, offset=op)
    raw = raw.reshape(rows // 8, rb // 16, 8, 16).transpose(0, 2, 1, 3).reshape(rows, rb) if flags & 1 else raw.reshape(rows, rb)
    if psm == 5:
        idx = raw
    else:
        idx = np.empty((rows, rb * 2), np.uint8); idx[:, 0::2] = raw & 15; idx[:, 1::2] = raw >> 4
    pal = np.frombuffer(b, np.uint8, count=nc * 4, offset=oc).reshape(nc, 4)
    texcache[ti] = pal[idx]
    return texcache[ti]


def slot_img(k):
    ti, u, v, w, h, x, y, _ = struct.unpack_from('<7Hh', b, oslot + k * 16)
    return tex_rgba(ti)[v:v + h, u:u + w], x, y


names = [t['name'] for t in layout]
if len(names) != struct.unpack_from('<4I', b, oscreen)[1]:
    die('layout.json не соответствует ui.shr (%d против %d элементов)' % (len(names), struct.unpack_from('<4I', b, oscreen)[1]))
imap = item(names.index('Map0'))
cx, cy = imap['px'], imap['py']
ring, rx, ry = slot_img(item(names.index('HnRMeterBgd'))['first'])
frame, fx, fy = slot_img(item(names.index('HnRMeterFrame'))['first'])
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
# внутренний край кольца шкалы: первый радиус, где средняя по углу альфа кольца >= 50% (из пикселей ui.shr)
ra = ring[..., 3].astype(np.float32) / 255
ry_, rx_ = np.mgrid[0:ring.shape[0], 0:ring.shape[1]].astype(np.float32)
rr = np.hypot(rx_ + 0.5 + rx - cx, ry_ + 0.5 + ry - cy)
R = next(r0 for r0 in np.arange(0, rr.max(), 0.25) if ((rr >= r0) & (rr < r0 + 0.25)).any() and ra[(rr >= r0) & (rr < r0 + 0.25)].mean() >= 0.5)
fmask = np.zeros((H, W), bool)
fm = frame[..., 3] >= 128
fmask[fy:fy + frame.shape[0], fx:fx + frame.shape[1]] = fm
lamp, lx, ly = slot_img(item(names.index('HitNRun'))['first'] + 2)  # мигалка над радаром: в покое кадр 2 (обе погашены, как PS2)
lmask = np.zeros((H, W), bool)
lmask[ly:ly + lamp.shape[0], lx:lx + lamp.shape[1]] = lamp[..., 3] >= 16
fring = np.zeros((H, W), bool)                                 # рамка с запасом 1 px (сглаживание краёв)
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        fring |= np.roll(np.roll(fmask, dy, 0), dx, 1)
print('круг радара: центр (%.1f, %.1f), внутренний край кольца шкалы R=%.2f px; Map0 r=%.1f, clip в ui.shr %.2f'
      % (cx, cy, R, imap['ang'], imap['clip']))

# ---- точки: дороги l1hudmap, ближайшие к углам карты ------------------------------------------------------
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import ui_export as U                                            # noqa: E402
m = U.bake_radar_map()
cls = np.asarray(m['img'])
ys_, xs_ = np.where(cls >= 2)
wx = m['x0'] + (xs_ + 0.5) / m['ss'] * m['mpp']; wz = m['z0'] + (ys_ + 0.5) / m['ss'] * m['mpp']
lo, hi = m['lo'], m['hi']
pts = [('empty', 5000.0, 5000.0, 0.0), ('center', 220.0, 172.0, 1.5708)]
for nm, (qx, qz) in (('nw', (lo[0], lo[1])), ('ne', (hi[0], lo[1])), ('sw', (lo[0], hi[1])), ('se', (hi[0], hi[1]))):
    k = int(np.argmin((wx - qx) ** 2 + (wz - qz) ** 2))
    pts.append((nm, float(wx[k]), float(wz[k]), 0.7))
print('точки: ' + ', '.join('%s (%.0f, %.0f)' % (n, x, z) for n, x, z, _ in pts))

# ---- прогон тестового EBOOT --------------------------------------------------------------------------------
D = args.out.resolve()
if D.exists():
    shutil.rmtree(D)
(D / 'win').mkdir(parents=True)
shutil.copy(args.eboot, D / 'EBOOT.PBP'); shutil.copy(args.shr, D / 'ui.shr')
bg = np.zeros((H, W, 4), np.uint8); bg[...] = BG + (255,)
(D / 'bg.raw').write_bytes(bg.tobytes())
(D / 'autoshot').write_bytes(b'')
(D / 'radar.txt').write_text(''.join('%s %.2f %.2f %.4f\n' % p for p in pts))
env = dict(**__import__('os').environ, PPSSPP_SHOTS=str(D / 'smoke.txt'), PPSSPP_SHOTDIR=str(D / 'win'))
subprocess.run([str(ROOT / 'tools/ppsspp_run.sh'), str(D / 'EBOOT.PBP'), '200'], env=env, check=False)
subprocess.run([sys.executable, str(ROOT / 'tests/ui/shots.py'), 'png', str(D)], check=False, capture_output=True)


def shot(n):
    p = D / ('shot_radar_%s.raw' % n)
    if not p.exists():
        die('нет снимка %s (эмулятор занят или упал)' % p.name)
    return np.frombuffer(p.read_bytes(), np.uint8).reshape(H, W, 4)[..., :3].astype(int)


empty = shot('empty')
fails, rows = [], []
for n, x, z, h in pts[1:]:
    diff = (np.abs(shot(n) - empty).sum(-1) > 24) & (RR <= imap['ang'] + 2)   # только радар: монеты и скорость тикают
    out = int((diff & (RR > R + 1.0)).sum()); inside = int((diff & (RR <= R)).sum())
    ok = out == 0 and inside >= 20
    rows.append('%-7s карта: внутри круга %4d px, за кругом %3d px (макс. радиус %.1f)  %s'
                % (n, inside, out, float(RR[diff].max()) if diff.any() else 0.0, 'ok' if ok else 'КРАСНОЕ'))
    if not ok:
        fails.append(n)
eb = np.abs(empty - np.array(BG)).sum(-1) > 24
cover = eb[fmask].mean() if fmask.any() else 0.0
rows.append('рамка: нарисовано %.0f%% её пикселей (нужно >= 80%%)  %s' % (cover * 100, 'ok' if cover >= 0.8 else 'КРАСНОЕ'))
if cover < 0.8:
    fails.append('рамка')
# мигалка рисуется последней из радара: её непрозрачные пиксели обязаны совпасть с картинкой кадра покоя по цвету
# (след рамки, диска и конуса под ней совпадения не дают; «отличается от фона» здесь слепая проверка)
lo = lamp[..., 3] >= 250
sh = empty[ly:ly + lamp.shape[0], lx:lx + lamp.shape[1]]
lcover = float((np.abs(sh[lo] - lamp[..., :3][lo].astype(int)).sum(-1) < 30).mean()) if lo.any() else 0.0
rows.append('мигалка: %.0f%% её непрозрачных пикселей совпали по цвету (нужно >= 80%%)  %s' % (lcover * 100, 'ok' if lcover >= 0.8 else 'КРАСНОЕ'))
if lcover < 0.8:
    fails.append('мигалка')
angle = np.degrees(np.arctan2(xx + 0.5 - cx, -(yy + 0.5 - cy)))  # 0 = вверх (конус смотрит вперёд)
cone = eb & (np.abs(angle) < 20) & (RR > R + 1.5) & (RR <= imap['ang'] + 1) & ~fring & ~lmask
rows.append('конус: пикселей за краем круга вне рамки %d  %s' % (int(cone.sum()), 'ok' if not cone.any() else 'КРАСНОЕ'))
if cone.any():
    fails.append('конус')
print('\n'.join(rows))
print('radar_clip: ' + ('PASS' if not fails else 'FAIL (' + ', '.join(fails) + ')') + '  снимки: ' + str(D.relative_to(ROOT)))
sys.exit(1 if fails else 0)
