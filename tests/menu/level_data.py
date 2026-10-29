#!/usr/bin/env python3
"""Ship only menu packs; validate album texts against Scrooby's disc bible.

The original 4:3 pages/rows are inventoried explicitly. This does not claim a
PS2 pixel/timing comparison (observer task 23 supplies that reference).
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import ui_export as U
import menu_export as M
import save_export as S

def strings(path):
    d=path.read_bytes(); h=struct.unpack_from('<32I',d)
    assert d[:4]==b'UIP1' and h[1]==1 and h[24]==len(d), f'{path}: UIP1 header'
    n,off=h[10:12]
    return h,[d[p:d.index(b'\0',p)].decode('latin1') for p in struct.unpack_from(f'<{n}I',d,off)]

def album(path,level):
    h,values=strings(path); assert h[6]==2, 'album/missionselect screen count'
    normalized={s.strip().casefold() for s in values}
    bible=U.load_bible(U.LANG)
    for k in range(7):
        nn=8*(level-1)+k
        title=bible(f'CARD_TITLE_{nn:02d}') or ''
        assert title and title.strip().casefold() in normalized, f'L{level} card{k} missing disc title {title!r}'
        episode=bible(f'CARD_EPISODE_{nn:02d}') or ''
        assert episode.strip().casefold() in normalized, f'L{level} card{k} missing episode {episode!r}'
    return h

def inventory():
    maps=[('pause','ingame.p3d','PauseSunday.scr',U.SCREEN_PAGES['pause']),
          ('pause-options','ingame.p3d','PauseOptions.scr',M.PAGES['pauseoptions']),
          ('pause-sound','ingame.p3d','PauseSound.scr',M.PAGES['pausesound']),
          ('pause-settings','ingame.p3d','PauseSettings.scr',M.PAGES['pausesettings']),
          ('album','ingame.p3d','PauseViewCards.scr',M.PAGES['viewcards']),
          ('mission-select','ingame.p3d','MissionSelect.scr',M.PAGES['missionselect']),
          ('front-options','frontend.p3d','Options.scr',M.PAGES['options']),
          ('front-sound','frontend.p3d','Sound.scr',M.PAGES['sound']),
          ('load','frontend.p3d','LoadGame.scr',S.PAGES['fslots']),
          ('save','ingame.p3d','SaveGame.scr',S.PAGES['pslots'])]
    report={}
    for name,project,screen,exported in maps:
        original=U.project(project).screens[screen]
        pages=[p for _,p in exported]
        report[name]=dict(disc_project=project,disc_screen=screen,disc_pages=original,exported_pages=pages,
                          omitted_pages=[p for p in original if p not in pages])
    report['phone-booth']=dict(disc_project='ingame.p3d',disc_screen='PhoneBooth.scr',disc_pages=U.project('ingame.p3d').screens['PhoneBooth.scr'],exporter='tools/shop_export.py')
    report['ps2_pixel_comparison']='blocked: observer task 23 not available'
    report['selection_pulse']='Claude-hover owns other-menu pulse; not modified'
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',default='build/menus-levels/stage');ap.add_argument('--export',action='store_true');ap.add_argument('--gate',action='store_true');a=ap.parse_args()
    stage=(ROOT/a.data).resolve();out=ROOT/'build/menus-levels';out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,SHIP_LEVELS='2 3 4 5 6 7',PATH=str(ROOT/'.venv/bin')+os.pathsep+os.environ['PATH'],SHR_TMP=str(out/'tmp'))
    rules=[r.split('|') for r in subprocess.check_output(['bash','tools/ship_files.sh','--rules'],cwd=ROOT,env=env,text=True).splitlines()]
    for level in range(1,8):
        folder=stage if level==1 else stage/f'l{level}';folder.mkdir(parents=True,exist_ok=True)
        for name in ['pextra.shr','pmenu.shr','psave.shr']:
            key=name if level==1 else f'l{level}/{name}'
            rows=[r for r in rules if r[0].strip()==key];assert len(rows)==1, f'missing shipping rule {key}'
            if a.export:
                command=rows[0][3].strip().replace('{out}',str(folder/name))
                with (out/f'export-l{level}-{name}.txt').open('w') as log:
                    p=subprocess.run(['bash','-c',command],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                    assert p.returncode==0, f'export {key}'
        qr=stage/f'cardqr-l{level}.bin'
        if a.export:
            with (out/f'export-l{level}-qr.txt').open('w') as log:
                subprocess.run([str(ROOT/'.venv/bin/python'),'tools/cardqr_export.py','--level',str(level),'--out',str(qr)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        album(folder/'pextra.shr',level)
        for name,count in [('pmenu.shr',3),('psave.shr',5)]:
            hdr,values=strings(folder/name);assert hdr[6]==count,(level,name,hdr[6])
        q=qr.read_bytes();assert q[:5]==b'CQR1\x07',f'L{level} QR card count'
        print(f'CHECK L{level} album=7/7 pause-options=3 save=5 QR=7 PASS',flush=True)
        if a.gate and level>1:
            try:album(stage/'pextra.shr',level)
            except AssertionError as error:print(f'CHECK L{level} OLD caught {error}',flush=True)
            else:raise AssertionError(f'L{level} L1 album not rejected')
    for name,count in [('menu.shr',4),('fsave.shr',5),('phone.shr',1)]:
        hdr,_=strings(stage/name);assert hdr[6]==count,(name,hdr[6])
    (out/'scrooby-inventory.json').write_text(json.dumps(inventory(),ensure_ascii=False,indent=2)+'\n')
    print('level menu data gate: PASS',flush=True)

if __name__=='__main__':main()
