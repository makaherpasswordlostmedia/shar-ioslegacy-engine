#!/usr/bin/env python3
"""Real post-FMV screen pixels and normal skip/cleanup, beyond generic smoke OK."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[2];run=Path(sys.argv[1]);text=(run/'smoke.txt').read_text();bad=[]
for needle in ['ENDING open','ENDING start blocks=32','ENDING close reason=skip','STREAM s=music track=credits','END']:
 if needle not in text:bad.append('missing '+needle)
im=np.asarray(Image.open(run/'ending_screen.png').convert('RGB')).astype(int)
for q in json.loads((root/'build/content/ending/gate.json').read_text())['figures']:
 x,y,w,h=q['dst'];a=im[max(0,y):min(272,y+h),max(0,x):min(480,x+w)]
 green=(a[:,:,1]>a[:,:,0]+10)&(a[:,:,1]>a[:,:,2]+10)&(a[:,:,1]>60)
 n=int(green.sum());print(q['name'],'visible green pixels',n)
 if n<250:bad.append(q['name']+' no real figure pixels')
for x in bad:print('FAIL',x)
print(('FAIL' if bad else 'PASS')+' ending native')
sys.exit(bool(bad))
