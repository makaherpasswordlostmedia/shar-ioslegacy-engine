#!/usr/bin/env python3
"""Measure actual UIP1 and GU trace frames against the original sprite silhouette.

OLD position packets fail centring. UI_OBJTOP_OLD native frames fail the later
visible-edge placement rule; this Kwik-E-Mart sample itself is not cropped.
All 150 silhouettes, including kburger, have a separate actual-C raster check.
"""
import argparse
import re
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/ui')]
import ui_export as U
import typo_bridge as B
import msnart_export as M

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('packet', type=Path)
ap.add_argument('run', type=Path)
a = ap.parse_args()
pack = B.parse(a.packet)
items = B.screen_items(pack, 0)
box = max((i for i in items if i[0] == U.T_IMG and i[2] == U.TAGS.index('OBJECTIVE')),
          key=lambda i: i[10] * i[11])
ring = max((i for i in items if i[0] == U.T_IMG and i[2] == U.TAGS.index('RADAR')),
           key=lambda i: i[10] * i[11])
radar_y = ring[9] + ring[11] / 2
sprite = U.all_images()['helptext.png']
bb = sprite.getchannel('A').point(lambda v: 255 if v >= 128 else 0).getbbox()
alpha_cy = (bb[1] + bb[3]) / (2 * sprite.height)
bad = []

def check(ok, message):
    print(('PASS ' if ok else 'FAIL ') + message)
    if not ok:
        bad.append(message)

check(abs(box[9] + box[11] * alpha_cy - radar_y) <= 1,
      f'packed visible bubble centre={box[9] + box[11] * alpha_cy:.2f} radar={radar_y:.2f}')
text = (a.run / 'smoke.txt').read_text()
scene = ''
last = {}
shots = {}
for line in text.splitlines():
    if line.startswith('SCENE '):
        scene = line.split()[1]
    if line.startswith(('UIBUBBLE ', 'UIAVATAR ')):
        last[(scene, line.split()[0])] = dict(re.findall(r'(\w+)=(\S+)', line))
    if line.startswith('SHOT '):
        shots[line.split()[1]] = dict(last)
check('END' in text.splitlines(), 'scenario reached END')
for name in ('bubble_avatar', 'bubble_noicon'):
    trace = shots.get(name, {}).get((name, 'UIBUBBLE'))
    check(trace is not None, name + ' actually drew bubble')
    if trace:
        cy = float(trace['y']) + float(trace['h']) * alpha_cy
        check(abs(cy - radar_y) <= 1 and float(trace['y']) + float(trace['h']) <= 272,
              f'{name} GU visible centre={cy:.2f} bottom={float(trace["y"]) + float(trace["h"]):.2f}')
    check((a.run / f'{name}.png').exists(), name + ' PNG retained')
avatar = shots.get('tall_top', {}).get(('tall_top', 'UIAVATAR'))
check(avatar is not None, 'collapsed tall avatar actually drew')
if avatar:
    # The script's goto stage advances to Kwik-E-Mart before the captured frame.
    # Do not claim that this native picture contains Krusty Burger.
    check('icon=kwike' in text, 'captured icon identified by real stage trace')
    source = M.export_file((U.WEB / 'source/game/art/frontend/dynaload/images/msnicons/location/kwike.p3d').resolve())
    _, ti, iw, ih = next(i for i in source.imgs if i[0] == 'kwike')
    tw, th, pixels = source.tex[ti]
    opaque = Image.frombytes('RGBA', (tw, th), pixels).crop((0, 0, iw, ih)).getchannel('A').point(lambda v: 255 if v >= 32 else 0).getbbox()
    x, y, w, h = (float(avatar[k]) for k in 'xywh')
    left, top = x + w * opaque[0] / iw, y + h * opaque[1] / ih
    bottom = y + h * opaque[3] / ih
    check(top >= 2 and bottom <= 272, f'visible tall silhouette bounds top={top:.2f} bottom={bottom:.2f}')
    check(abs(top - max(2, left)) <= 1, f'visible edge margin top={top:.2f} left={left:.2f}')
check((a.run / 'tall_top.png').exists(), 'collapsed avatar PNG retained')
print(f'RESULT {"FAIL" if bad else "PASS"} failures={len(bad)}')
raise SystemExit(bool(bad))
