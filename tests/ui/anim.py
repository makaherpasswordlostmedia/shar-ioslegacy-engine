#!/usr/bin/env python3
"""Хост-гейт анимаций HUD: математика viewer/ui_anim.h по кадрам 60 Гц (tests/ui/anim.c) против правил anim_rules.py;
кольцо Hit & Run — против оригинала (правка Роба 241): режимы и ритм мигания (запись PS2), дуга (viewer/ui_radial.h против
замера близнецов) и цвета заливки (константы ui_anim.h против кадров близнеца tw_hnr_text без сжатия).

    python tests/ui/anim.py                      # зелёное: код 0
    python tests/ui/anim.py --mode old           # код кольца до 28.09 — обязан быть красным (код 1)
    python tests/ui/anim.py --mode pre241        # кольцо до правки 241 (дуга, цвета, режимы) — обязано быть красным
    python tests/ui/anim.py --src ПАПКА          # тот же гейт на чужом коде: ПАПКА/viewer/*.h и ПАПКА/tests/ui/anim.c
                                                 # (прежний код до правки 241 — обязан быть красным)
    python tests/ui/anim.py --mode nopulse       # △ без пульса — красное
    python tests/ui/anim.py --mode nopop         # уведомления без всплывания — красное
Кадры близнеца: build/twins/o4/tw_hnr_text/png (папка данных — SHAR_DATA, по умолчанию корень репозитория)."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import anim_rules as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('SHAR_DATA', ROOT))
ap = argparse.ArgumentParser()
ap.add_argument('--mode', default='new', choices=['new', 'old', 'pre241', 'nopulse', 'nopop'])
ap.add_argument('--src', type=Path, default=ROOT)
args = ap.parse_args()
src = args.src.resolve()
tmp = Path(tempfile.mkdtemp())
subprocess.run(['cc', '-std=c99', '-O1', '-I', str(src / 'viewer'), str(src / 'tests/ui/anim.c'), '-lm', '-o', str(tmp / 'anim')], check=True)
subprocess.run(['cc', '-std=c99', '-O1', '-I', str(src / 'viewer'), str(Path(__file__).with_name('arc.c')), '-lm', '-o', str(tmp / 'arc')], check=True)
lines = subprocess.check_output([str(tmp / 'anim'), args.mode], text=True).splitlines()
pulse, hnr, pin, pout = [], [], {0: [], 1: []}, {0: [], 1: []}
for ln in lines:
    p = ln.split()
    if p[0] == 'PULSE':
        pulse.append((float(p[1]), float(p[2])))
    elif p[0] == 'HNR':   # 6-й столбец (полиция) — с правки 241; у прежнего кода полиция = шкала 100 (его сценарий)
        hnr.append((float(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5], 16)) + ((int(p[6]),) if len(p) > 6 else ()))
    elif p[0] == 'POPIN':
        pin[int(p[1])].append((float(p[2]), float(p[3]), float(p[4])))
    elif p[0] == 'POPOUT' and int(p[5]):
        pout[int(p[1])].append((float(p[2]), float(p[4])))
arc = [tuple(map(float, l.split()[1:])) for l in subprocess.check_output([str(tmp / 'arc'), args.mode], text=True).splitlines() if l.startswith('ARC')]


def twin_colours():
    """заливка кольца у близнеца tw_hnr_text (кадры PCSX2 682x512 без сжатия): медиана полосы кольца (центр 563.3,404.2,
    r 52.8 — круг по красным пикселям нижней половины кадра 151) на 60..300° от 12 часов"""
    from PIL import Image
    d = DATA / 'build/twins/o4/tw_hnr_text/png'
    if not d.is_dir():
        return None
    yy, xx = np.mgrid[0:512, 0:682]
    rr = np.hypot(xx - 563.3, yy - 404.2); ang = (np.degrees(np.arctan2(xx - 563.3, -(yy - 404.2))) + 360) % 360
    band = (np.abs(rr - 52.8) < 2.0) & (ang > 60) & (ang < 300)
    out = {}
    for name, frames in (('RED', (151, 172, 199, 202)), ('BLUE', (190, 193, 208, 211)), ('DARK', (160, 163, 166, 184))):
        px = np.concatenate([np.asarray(Image.open(d / ('f%05d.png' % f)).convert('RGB')).astype(int)[band] for f in frames])
        out[name] = np.median(px, 0)
    return out


def header_colour(name):
    if args.mode == 'pre241':   # константы кольца до правки 241 — цвета горящих половин мигалки, чёрного не было
        v = {'RED': 0xff1f25dc, 'BLUE': 0xffb35038}.get(name)
        return None if v is None else np.array([v & 255, (v >> 8) & 255, (v >> 16) & 255])
    m = re.search(r'#define\s+UI_HNR_%s\s+0x([0-9a-fA-F]{8})u' % name, (src / 'viewer/ui_anim.h').read_text(encoding='utf-8'))
    if not m:
        return None
    v = int(m.group(1), 16)
    return np.array([v & 255, (v >> 8) & 255, (v >> 16) & 255])


results = []
results.append(R.report('пульс △', R.pulse(pulse)))
results.append(R.report('кольцо Hit & Run', R.hnr(hnr)))
for k, nm in ((0, 'надпись'), (1, 'рамка задания')):
    results.append(R.report('всплывание: %s' % nm, R.pop_in(pin[k], k) + R.pop_out(pout[k])))
results.append(R.report('дуга кольца (viewer/ui_radial.h против близнецов)', R.arc(arc)))
tw = twin_colours()
cc = []
if tw is None:
    cc.append((False, 'нет кадров близнеца %s' % (DATA / 'build/twins/o4/tw_hnr_text/png')))
else:
    for name in ('RED', 'BLUE', 'DARK'):
        h = header_colour(name)
        ok = h is not None and all(abs(int(a) - int(b)) <= 8 for a, b in zip(h, np.round(tw[name])))
        cc.append((ok, 'UI_HNR_%s: в коде %s, у близнеца %s (± 8)' % (name, h.tolist() if h is not None else 'нет', np.round(tw[name]).astype(int).tolist())))
results.append(R.report('цвета заливки кольца (ui_anim.h против близнеца tw_hnr_text)', cc))
ok = all(r[0] for r in results)
print(('anim host: OK' if ok else 'anim host: КРАСНОЕ') + ' (режим %s, код %s)' % (args.mode, src))
for _, text in results:
    print(text)
sys.exit(0 if ok else 1)
