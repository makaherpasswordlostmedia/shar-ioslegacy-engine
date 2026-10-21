#!/usr/bin/env python3
"""Actual L7 final-stage event -> production hook; --eof also proves unchanged credits clock.
Normal checker on C3_ENDING_OLD must fail; --guard-old verifies that old branch separately.
"""
import json,re,sys
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[2];run=Path(sys.argv[1]);text=(run/'smoke.txt').read_text();bad=[]
old='--guard-old' in sys.argv;eof='--eof' in sys.argv
need=['MENULEVEL n=7 set=7','LEVEL ev=now n=7 loaded=7','MSN mainat m8 stage=1',
      'MSN level-complete level=7 gameover=1','LEVELDONE n=7 code=2']
indices=[]
for n in need:
 i=text.find(n);indices.append(i)
 if i<0:bad.append('missing '+n)
if indices!=sorted(indices):bad.append('event chain out of order')
ld=re.search(r'LEVELDONE n=7 code=2[^\n]*t=([\d.]+)',text)
menus=list(re.finditer(r'MENU n=2[^\n]*t=([\d.]+)',text))
if not menus or not ld or menus[0].start()<ld.start():bad.append('no normal frontend return after ld2')
if old:
 if 'ENDING ' in text:bad.append('OLD guard entered ending')
 if ld and menus and abs(float(menus[0][1])-float(ld[1]))>.2:bad.append('OLD guard delayed frontend')
else:
 for n in ['ENDING open','ENDING start blocks=32 lines=399','STREAM s=music track=credits',
           'ENDING close reason='+('end' if eof else 'skip')]:
  if n not in text:bad.append('missing '+n)
 opened=text.find('ENDING open')
 if opened>=0 and opened<indices[-1]:bad.append('ending precedes real ld2')
 a=np.asarray(Image.open(run/'ending_screen.png').convert('RGB')).astype(int)
 for q in json.loads((root/'build/content/ending/gate.json').read_text())['figures']:
  x,y,w,h=q['dst'];p=a[y:y+h,x:x+w];n=int(((p[:,:,1]>p[:,:,0]+10)&(p[:,:,1]>p[:,:,2]+10)&(p[:,:,1]>60)).sum())
  print(q['name'],'visible green pixels',n)
  if n<250:bad.append(q['name']+' missing art')
 if eof:
  start=re.search(r'ENDING start blocks=32 lines=399 end=([\d.]+) speed=([\d.]+)',text)
  close=re.search(r'ENDING close reason=end scroll=([\d.]+) blocks=32',text)
  if not start or not close:bad.append('no measured natural EOF')
  else:
   end,speed,scroll=float(start[1]),float(start[2]),float(close[1])
   if abs(speed-35*272/480)>.0001:bad.append('credits speed changed')
   if not end<=scroll<=end+1:bad.append('EOF before/after last line boundary')
   if ld and menus:
    elapsed=float(menus[0][1])-float(ld[1]);print('EOF elapsed emulated seconds',elapsed,'scroll',scroll,'speed',speed)
    if abs(elapsed*speed-scroll)>2:bad.append('EOF clock accelerated or slowed')
for n in ['END']:
 if not re.search(r'^'+n+r'$',text,re.M):bad.append('no END')
for x in bad:print('FAIL',x)
print(('FAIL' if bad else 'PASS')+' L7 production integration'+(' OLD guard branch' if old else ' natural EOF' if eof else ' checkpoint Back'))
sys.exit(bool(bad))
