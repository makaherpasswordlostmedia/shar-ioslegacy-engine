#!/usr/bin/env python3
"""Corrupt the packed font atlas; new linked pause gate must see it, OLD misses it."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
out=Path(tempfile.mkdtemp(prefix='pause-font-link-',dir=ROOT/'build'))
(out/'ui').mkdir()
for pack,layout in [('ui.shr','layout.json'),('menu.shr','layout_menu.json'),('pmenu.shr','layout_pmenu.json'),('pextra.shr','layout_pextra.json')]:
    shutil.copy2(ROOT/'build'/pack,out/pack)
    shutil.copy2(ROOT/'build/ui'/layout,out/'ui'/layout)
b=bytearray((out/'ui.shr').read_bytes())
hdr=struct.unpack_from('<4s19I',b)
otex,ofont=hdr[3],hdr[9]
for fi in range(hdr[8]):
    ti=struct.unpack_from('<H',b,ofont+fi*(16+8*256))[0]
    rec=struct.unpack_from('<4H6I',b,otex+ti*32)
    oc,nc=rec[5],rec[6]
    for c in range(nc):b[oc+c*4+3]=0
(out/'ui.shr').write_bytes(b)
for tag,extra,wanted in [('new',{},1),('old',{'PAUSE_FONT_CHECK_OLD':'1'},0)]:
    p=subprocess.run([sys.executable,'tests/pause_layout/check.py','--font-dir',str(out)],cwd=ROOT,
                     env=dict(os.environ,**extra),text=True,capture_output=True)
    (out/(tag+'.txt')).write_text(p.stdout+p.stderr)
    assert p.returncode==wanted,(tag,p.stdout,p.stderr)
    if tag=='new':assert 'menu_font_check' in p.stdout and 'КРАСНЫЙ' in p.stdout
print('PASS: corrupted real atlas fails linked gate; OLD unlinked gate misses corruption')
