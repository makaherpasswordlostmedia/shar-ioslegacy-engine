#!/usr/bin/env python3
"""Check normal controller navigation, collected-card zoom and real screen frames.
The all-level scenario opens via pause buttons; no direct UI-open fixture.
"""
import argparse
from pathlib import Path
import re
import numpy as np
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('report');a=ap.parse_args();root=Path(a.report)
    log=(root/'smoke.txt').read_text(errors='replace');fails=[]
    if not re.search(r'^END\b',log,re.M):fails.append('no END')
    for level in range(1,8):
        m=re.search(rf'^SCENE menus_l{level}\b.*?(?=^SCENE |^END|\Z)',log,re.M|re.S)
        block=m.group(0) if m else ''
        for needle in ['VIEWCARDS open sel=0 zoom=0 got=127','VIEWCARDS zoom sel=0 zoom=1 got=127','VIEWCARDS zoom sel=6 zoom=1 got=127','VIEWCARDS close',
                       'OPT pack=pmenu scr=0','OPT pack=pmenu scr=1','OPT pack=pmenu scr=2','SVOPEN mode=save']:
            if needle not in block:fails.append(f'L{level} missing {needle}')
        images={}
        for name in ['pause','album','card0','card6','options','sound','settings','save']:
            file=root/f'l{level}_{name}.png'
            if not file.exists():fails.append(f'L{level} missing {name} image');continue
            image=np.asarray(Image.open(file).convert('RGB'));images[name]=image
            if image.shape != (272,480,3):fails.append(f'L{level} {name} frame size')
            if len(np.unique(image.reshape(-1,3),axis=0))<100:fails.append(f'L{level} {name} empty frame')
        if 'card0' in images and 'card6' in images:
            # BigCard lives in the left board. Ignore the description, QR and HUD.
            p=images['card0'][50:220,45:177].astype('int16');q=images['card6'][50:220,45:177].astype('int16')
            n=int((np.abs(p-q).max(axis=2)>30).sum())
            if n<500:fails.append(f'L{level} card0/card6 same illustration ({n} pixels)')
            print(f'CHECK L{level} distinct_card_art changed_pixels={n}')
        print(f'CHECK L{level} menus {"FAIL" if any(f.startswith(f"L{level} ") for f in fails) else "PASS"}')
    for f in fails:print('FAIL',f)
    print('level menus emulator: '+('FAIL' if fails else 'PASS'))
    return bool(fails)

if __name__=='__main__':raise SystemExit(main())
