#!/usr/bin/env python3
"""Правка 249: проверка прогонов tests/skid/scenario.txt (зелёный и красный «flag skidoff» одним EBOOT).
   emu_check.py ЗЕЛЁНЫЙ_DIR КРАСНЫЙ_DIR   -> 0 зелёный
Журнал (smoke.txt, строки SKID после торможения): в зелёном квадов > 0 и нарисовано > 0, уровень заноса машины в торможении 1;
в красном квадов 0. Снимки skid_brake/skid_after: машина в том же месте (SHOT pos), а позади задних колёс зелёный темнее красного
больше чем на 12 по яркости не меньше чем в MIN_PX точках (следы видно), остальной кадр совпадает (следы ничего не сдвигают)."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

MIN_PX = 500


def skid_lines(d):
    out = []
    for l in (Path(d) / 'smoke.txt').read_text(errors='replace').splitlines():
        if l.startswith('SKID '):
            out.append({k: float(v) for k, v in re.findall(r'(\w+)=([-\d.]+)', l)})
    return out


def shots(d):
    return {m.group(1): tuple(map(float, m.group(2).split()[:3])) for m in
            re.finditer(r'^SHOT (\S+) [\d.]+ pos (.*)$', (Path(d) / 'smoke.txt').read_text(errors='replace'), re.M)}


def lum(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(np.int16)
    return (a[..., 0] * 77 + a[..., 1] * 150 + a[..., 2] * 29) >> 8


def main(g, r):
    bad = 0
    sg, sr = skid_lines(g), skid_lines(r)
    if len(sg) < 4 or len(sr) < 4:
        print(f'  мало строк SKID: зелёный {len(sg)}, красный {len(sr)}'); return 1
    brake = max(sg, key=lambda x: x['lvl'])
    print(f"  зелёный: после газа квадов {sg[1]['quads']:.0f}, в торможении квадов {sg[2]['quads']:.0f} (уровень {sg[2]['lvl']:.2f}, "
          f"тянутся {sg[2]['live']:.0f}), после стопа {sg[3]['quads']:.0f}, нарисовано {sg[3]['drawn']:.0f}; "
          f"мкс на кадр до {max(x['us'] for x in sg):.0f}")
    print(f"  красный: квадов {max(x['quads'] for x in sr):.0f}")
    if not (sg[3]['quads'] > 0 and sg[3]['drawn'] > 0): print('  ЗЕЛЁНЫЙ: следов нет'); bad = 1
    if brake['lvl'] != 1.0: print(f"  ЗЕЛЁНЫЙ: уровень заноса в торможении {brake['lvl']} (ждём 1 — тормоз на 7–50 % TopSpeed)"); bad = 1
    if max(x['quads'] for x in sr) != 0: print('  КРАСНЫЙ: следы есть при flag skidoff'); bad = 1
    pg, pr = shots(g), shots(r)
    for s in ('skid_brake', 'skid_after'):
        if s not in pg or s not in pr: print(f'  нет снимка {s}'); bad = 1; continue
        if max(abs(a - b) for a, b in zip(pg[s], pr[s])) > .05:
            print(f'  {s}: машина в разных местах {pg[s]} / {pr[s]} — сравнение снимков не годится'); bad = 1; continue
        a, b = lum(Path(g) / f'{s}.png'), lum(Path(r) / f'{s}.png')
        d = b - a
        roi = d[190:272, 100:380]
        dark, other = int((roi > 12).sum()), int((np.abs(d) > 12).sum()) - int((roi > 12).sum())
        print(f'  {s}: позади машины темнее на >12 — {dark} точек (средне на {roi[roi > 12].mean() if dark else 0:.1f}), вне этого отличий {other}')
        if dark < MIN_PX: print(f'  {s}: следов на снимке не видно (< {MIN_PX})'); bad = 1
        if other > 200: print(f'  {s}: кадр отличается не только следами'); bad = 1
    return bad


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
