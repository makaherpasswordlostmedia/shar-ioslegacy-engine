#!/usr/bin/env python3
"""№890/№891 (Роб 23.10: «Picture первым пунктом в Options; внутри Picture — Cartoon первым, видно что это подменю: стрелка › справа»).
По раскладке пакета pmenu (tools/menu_export.py, без эмулятора):
  890: первая строка OPTIONS паузы — PICTURE, затем SOUND, CAMERA, GAME;
  891: первая строка PICTURE — Cartoon, после неё Saturation, Contrast, Tree Shadows, Draw Distance; у строки Cartoon справа постоянная «>» (элемент CartoonLink_Chev),
       стоящая правее подписи и на её высоте; у остальных строк такой «>» нет.
  order_check.py [--old]   0 = PASS; --old (OPT_PICTURE_FIRST_OLD=1 PICTURE_CARTOON_FIRST_OLD=1 LINK_CHEV_OLD=1, красный контроль): 0 только если упало"""
import os, sys
from pathlib import Path
old = '--old' in sys.argv
if old:
    os.environ.update(OPT_PICTURE_FIRST_OLD='1', PICTURE_CARTOON_FIRST_OLD='1', LINK_CHEV_OLD='1')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); os.environ.setdefault('UI_SCRATCH', '/tmp/menu890_scratch')
import ui_export as U, menu_export as M
assets = U.Assets(); fonts = U.FontCache('psp')


def rows(sc):
    U.SCREEN_PAGES[sc] = M.PAGES[sc]
    its = M.build(sc, assets, fonts)
    lab = sorted((t for t in its if t['type'] == U.T_TEXT and t.get('menu', -1) >= 0 and t['strings'] and t.get('flags', 0) is not None), key=lambda t: t['menu'])
    return its, [(t['menu'], t['strings'][0]) for t in lab if t['name'] == t['name'].split('_')[0] and not t['name'].endswith('_Value')]


errs = []
its, ro = rows('pauseoptions'); names = [s.upper() for _, s in ro]
print('  OPTIONS:', names)
if names[:4] != ['PICTURE', 'SOUND', 'CAMERA', 'GAME']: errs.append(f'порядок OPTIONS {names}')
its, rp = rows('pausepicture'); names = [s.upper() for _, s in rp]
print('  PICTURE:', names)
names = [n for n in names if n != 'TEXTURES']   # №912: строка Textures (мультик без текстур) сразу после Cartoon — допустима
if names[:5] != ['CARTOON', 'SATURATION', 'CONTRAST', 'TREE SHADOWS', 'DRAW DISTANCE']: errs.append(f'порядок PICTURE {names}')
chev = [t for t in its if t['name'].endswith('_Chev')]
lab = next((t for t in its if t['name'] == 'CartoonLink' and t['type'] == U.T_TEXT), None)
if len(chev) != 1: errs.append(f'«>» перехода: {len(chev)} элементов (нужен один)')
elif lab is not None:
    c = chev[0]; cy = c['rect'][1] + c['rect'][3] / 2; ly = lab['rect'][1] + lab['rect'][3] / 2
    print(f'  «>» x {c["rect"][0]:.0f}..{c["rect"][0] + c["rect"][2]:.0f}, центр y {cy:.1f} (подпись {ly:.1f}), знак {c["strings"]}')
    if c['strings'] != ['>'] or c['rect'][0] + c['rect'][2] / 2 <= lab['rect'][0] + lab['rect'][2] / 2: errs.append('«>» не справа от подписи')
    if abs(cy - ly) > 6: errs.append('«>» не на высоте подписи')
ok = not errs
for e in errs: print('  FAIL', e)
print(('PASS' if ok else 'FAIL') + f' · tests/menu890/order_check.py{" --old" if old else ""}')
sys.exit((0 if not ok else 1) if old else (0 if ok else 1))
