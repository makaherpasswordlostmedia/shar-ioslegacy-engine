#!/usr/bin/env python3
"""386: raster bounds of every original objective avatar, including tall silhouettes.
Runs the actual C placement helper; --red uses the previous frame-top placement.
"""
import ctypes, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U
import msnart_export as M
red = '--red' in sys.argv
with tempfile.TemporaryDirectory(prefix='shar-edge-') as td:
    c = Path(td) / 'edge.c'; lib = Path(td) / 'edge.so'
    c.write_text('#include "ui_edge_padding.h"\nfloat shift(int x,int y,int w,int h,int iw,int ih,int l,int t){return uiIconTopShift(x,y,w,h,iw,ih,l,t);}')
    subprocess.run(['cc','-shared','-fPIC','-I'+str(ROOT/'viewer'),str(c),'-o',str(lib)],check=True)
    fn = ctypes.CDLL(str(lib)).shift
    fn.argtypes = [ctypes.c_int]*8; fn.restype = ctypes.c_float
    items, icons = U.build_items('hud')
    dl, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
    bx, by, bw, bh = next(t for t in dl if t['name']=='ObjectiveIcon')['extframe']
    count = bad = raised = 0
    for path in sorted((U.WEB/'source/game/art/frontend/dynaload/images/msnicons').glob('*/*.p3d')):
        e = M.export_file(path)
        for name, ti, iw, ih in e.imgs:
            tw, th, pixels = e.tex[ti]
            im = Image.frombytes('RGBA',(tw,th),pixels).crop((0,0,iw,ih))
            box = im.getchannel('A').point(lambda a:255 if a>=32 else 0).getbbox()
            if not box: continue
            dy = 1-by if red else round(fn(bx,by,bw,bh,iw,ih,box[0],box[1]))
            # Independent raster observation after the same fit used by drawExt.
            scale = min(bw/iw,bh/ih)
            canvas = Image.new('L',(480,272))
            sized = im.getchannel('A').resize((round(iw*scale),round(ih*scale)),Image.Resampling.BILINEAR)
            canvas.paste(sized,(round(bx+(bw-iw*scale)/2),round(by+(bh-ih*scale)/2)+dy))
            b = canvas.point(lambda a:255 if a>=32 else 0).getbbox()
            count += 1; raised += dy < 1-by
            if b is None or b[1]<2 or abs(b[1]-max(2,b[0]))>1:
                bad+=1; print('FAIL',path.stem,name,b)
    print(f'avatars={count} bad={bad} higher_than_previous={raised} red={red}')
    if not count or bad: sys.exit(1)
