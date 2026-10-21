#!/usr/bin/env python3
"""381: measure raster capitals in every failure-screen font from the exported UIP1 pack.
Use --pack with the previous ui.shr as the negative control.
"""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import ui_export as U
from typo_bridge import parse, screen_items
ap=argparse.ArgumentParser(); ap.add_argument('--pack',type=Path,required=True); args=ap.parse_args()
p=parse(args.pack); bad=0; count=0
for it in screen_items(p,U.SCREENS.index('missionover')):
    if it[0]!=U.T_TEXT: continue
    face=p['fonts'][it[16]]['name']; cap=U.cap_px(face)
    count+=1
    if cap<9: bad+=1
    print(('FAIL' if cap<9 else 'PASS'),face,'capital',cap,'px')
print('failure texts',count,'bad',bad)
sys.exit(1 if bad or count<6 else 0)
