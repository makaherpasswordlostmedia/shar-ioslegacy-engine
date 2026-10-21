#!/usr/bin/env python3
"""Real seventh card -> native seven-track screen; verify closed-icon tint pixels."""
from pathlib import Path
import sys,numpy as np
from PIL import Image
import unlock_emu as U
import screens_check as C
import screens_export as E
U.OUT=U.ROOT/'build/gates/bonus_screens';U.OUT.mkdir(parents=True,exist_ok=True)
scen=U.scen_new().replace('flag menu\n','flag menu\nflag bonusshots 1\n',1)
d,bad=U.run('locked-native',Path(sys.argv[1]).resolve(),scen,timeout=300)
f,notes,_=U.check_new(d,bad);assert not f,f
s=next(U.kv(l) for l in U.lines(d) if l.startswith('BONUS ev=uistate scr=mmtrack '));assert s['open']=='01'
r=C.pack_res();k=int(s['chr']);mask=int(s['open'],16)
st={'show':{'ALWAYS',E.CUR_TAGS[k]},'ROW5':int(s['veh']),'ROW6':int(s['rate']),'ROW7':1,'ROW%d'%k:1}
st2={'show':{'ALWAYS',E.CUR_TAGS[int(s['track'])-1],*E.TRACK_TAGS},'ROW9':int(s['laps']),'ROW10':int(s['rev'])}
bright=C.overlay([('mmchar',st,-1),('mmtrack',st2,-1),('mmhints',{'show':{'ALWAYS'}},-1)])
dl=[]
for item in r['screens']['mmtrack']:
 q=dict(item)
 if q['tag'] in E.TRACK_TAGS and not mask&(1<<E.TRACK_TAGS.index(q['tag'])):
  q['color']=[(v*64+127)//255 for v in q.get('color',[255]*4)[:3]]+[q.get('color',[255]*4)[3]]
 dl.append(q)
r['screens']['mmtrack_locked']=dl
dim=C.overlay([('mmchar',st,-1),('mmtrack_locked',st2,-1),('mmhints',{'show':{'ALWAYS'}},-1)])
a=np.asarray(Image.open(d/'bonus_mmtrack.png').convert('RGB'),float);b=np.asarray(bright,float);c=np.asarray(dim,float)
m=(np.abs(b[:,:,:3]-c[:,:,:3]).max(axis=2)>30)&(c[:,:,3]>=250)
n=int(m.sum());ed=float(np.abs(a[m]-c[:,:,:3][m]).mean()) if n else float('inf');eb=float(np.abs(a[m]-b[:,:,:3][m]).mean()) if n else float('inf')
print('native:',d,'closed-icon pixels:',n,'dim error:',ed,'bright error:',eb)
assert n>=100 and ed<=10 and eb>10
print('PASS real card unlock / closed navigation / native six dim icons')
