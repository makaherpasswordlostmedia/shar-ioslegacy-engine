#!/usr/bin/env python3
"""Ending disc -> UIP1; --old must fail real-art pixel/slot checks."""
import json,os,sys,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests/ui'))
import ui_export as U
import ending_export as E
import typo_bridge as B
out=ROOT/'build/content/ending';out.mkdir(parents=True,exist_ok=True)
old='--old' in sys.argv
if old:os.environ['ENDING_ASSETS_OLD']='1'
path=out/('ending-old.shr' if old else 'ending.shr');r=E.export(path)
p=U.project('ingame.p3d');expect={e['name']:e for _,e in U.iter_leaves(p.pages['CreditsKK.pag']) if e['kind']=='sprite'}
dl=r['screens']['ending'];raw=B.parse(path);errors=[]
def check(ok,msg):
 print(('PASS ' if ok else 'FAIL ')+msg)
 if not ok:errors.append(msg)
check(p.screens['CreditsPostFMV.scr']==['CreditsBgd.pag','ViewCredits.pag','CreditsKK.pag'],'authored screen pages')
blocks=[t for t in dl if t['type']==U.T_TEXT and t['tag']=='SKIP']
source={e['name']:e for _,e in U.iter_leaves(p.pages['ViewCredits.pag'])}
check([t['name'] for t in blocks]==['Credits%d'%i for i in range(32)],'all 32 blocks in numeric order')
check(all(t['strings']==[q['text'] or '' for q in source[t['name']]['strings']] for t in blocks),'disc bible text exactly')
packed=[it for it in B.screen_items(raw,0) if it[0]==3 and it[2]==U.TAGS.index('SKIP')]
check(len(packed)==32,'UIP1 contains 32 actual credit text records')
provenance=[]
for name,e in expect.items():
 t=next(q for q in dl if q['name']==name);key=name.lower()+'.png';x,y,w,h=t['dst']
 src=U.ROOT/'hit-and-run-web/source/game/art/frontend/dynaload/images'/(name.lower()+'.p3d')
 _,im=U.decode_sprite_image(next(c for c in U.read(src).children if c.id==U.C_IMAGE))
 check(t['frames']==[key],name+' actual dynaload image replaces dot')
 check(abs(w/h-im.width/im.height)<.02 and w>50 and h>65,name+' source aspect and visible size')
 ox=0 if e['x']<U.SRC_W/3 else U.DST_W-U.SRC_W*U.S if e['x']>2*U.SRC_W/3 else (U.DST_W-U.SRC_W*U.S)/2
 check(abs(x+w/2-(e['x']*U.S+ox))<=1 and abs(y+h/2-(U.SRC_H-e['y'])*U.S)<=1,name+' authored centre with standard widescreen anchor')
 a=np.asarray(r['qbitmaps'][t['bitmaps'][0]].convert('RGBA')).astype(int);green=(a[:,:,1]>a[:,:,0]+10)&(a[:,:,1]>a[:,:,2]+10)&(a[:,:,3]>40)
 check(int(green.sum())>400,name+' real coloured figure pixels '+str(int(green.sum())))
 provenance.append(dict(name=name,dst=list(map(int,t['dst'])),green=int(green.sum())))
 # Verify actual packed bitmap slot dimensions; no metadata-only dummy can pass
 check(any(it[0]==2 and list(it[8:12])==list(t['dst']) for it in B.screen_items(raw,0)),name+' real UIP1 image item')
check([t['name'] for t in dl[-4:]]==['Kodos','Kang','Bottom','Top'],'authored figures then black-bar foreground order')
(out/('gate-old.json' if old else 'gate.json')).write_text(json.dumps(dict(errors=errors,figures=provenance),indent=2))
print(('FAIL' if errors else 'PASS')+' ending data '+str(len(errors))+' errors')
sys.exit(bool(errors))
