#!/usr/bin/env python3
"""Count lost opaque pixels of all original avatars using the actual UIP1 slot.

New placement executes uiIconTopShift in C; --old uses UI_OBJTOP_OLD's
OBJ_TOP_Y - it->y expression, also independently tested in native frames.
"""
import argparse
import ctypes
import json
import math
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/ui')]
import ui_export as U
import typo_bridge as B
import msnart_export as M

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('packet', type=Path)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--old', action='store_true')
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
c, so = a.out / 'placement.c', a.out / 'placement.so'
c.write_text('#include "ui_edge_padding.h"\nfloat shift(int x,int y,int w,int h,int iw,int ih,int l,int t){return uiIconTopShift(x,y,w,h,iw,ih,l,t);}\n')
subprocess.run(['cc', '-shared', '-fPIC', '-I' + str(ROOT / 'viewer'), str(c), '-o', str(so)], check=True)
fn = ctypes.CDLL(str(so.resolve())).shift
fn.argtypes = [ctypes.c_int] * 8
fn.restype = ctypes.c_float
pack = B.parse(a.packet)
it = next(i for i in B.screen_items(pack, 0) if i[0] == U.T_SLOT and i[3] == U.FIELDS.index('OBJICON'))
bx, by, bw, bh = map(round, (it[20], it[21], it[22], it[24]))
rows = []
for path in sorted((U.WEB / 'source/game/art/frontend/dynaload/images/msnicons').glob('*/*.p3d')):
    entry = M.export_file(path)
    for name, ti, iw, ih in entry.imgs:
        tw, th, pixels = entry.tex[ti]
        alpha = Image.frombytes('RGBA', (tw, th), pixels).crop((0, 0, iw, ih)).getchannel('A')
        bb = alpha.point(lambda v: 255 if v >= 32 else 0).getbbox()
        if not bb:
            continue
        scale = min(bw / iw, bh / ih)
        solid = alpha.resize((round(iw * scale), round(ih * scale)), Image.Resampling.BILINEAR).point(lambda v: 255 if v >= 32 else 0)
        count = int(np.count_nonzero(np.asarray(solid)))
        shift = 1 - it[9] if a.old else math.floor(fn(bx, by, bw, bh, iw, ih, bb[0], bb[1]) + .5)
        canvas = Image.new('L', (480, 272))
        canvas.paste(solid, (round(bx + (bw - iw * scale) / 2), round(by + (bh - ih * scale) / 2) + shift))
        lost = count - int(np.count_nonzero(np.asarray(canvas)))
        rows.append(dict(file=str(path.relative_to(U.WEB)), name=name, lost=lost, bbox=canvas.getbbox()))
bad = [r for r in rows if r['lost']]
(a.out / 'icons.json').write_text(json.dumps(rows, indent=2))
for row in bad:
    print(f'FAIL {row["name"]} lost={row["lost"]} bbox={row["bbox"]}')
ok = bool(rows) and not bad
print(f'RESULT {"PASS" if ok else "FAIL"} avatars={len(rows)} clipped={len(bad)} old={a.old}')
raise SystemExit(not ok)
