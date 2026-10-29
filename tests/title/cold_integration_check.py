#!/usr/bin/env python3
"""Independent saved-data cold FE acceptance. Never launches an emulator or changes RUN.
Check logos -> START-only title with >=60s/no demo -> clip4 -> room; first unmasked GU pulse.
--plants proves the checker rejects five in-memory corruptions; no fixture budget is spent.
"""
import argparse,re,sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
from start_phase_check import fit,PS_P,PS_P_TOL,PS_R,PS_R_TOL,CENTER_TOL

def fields(line):return dict(re.findall(r'(\w+)=([^\s]+)',line))
def check(run,log,intro):
    lines=log.splitlines();bad=[];notes=[]
    def rows(prefix):return [(i,fields(s)) for i,s in enumerate(lines) if s.startswith(prefix)]
    def find(prefix,**want):return next(((i,k) for i,k in rows(prefix) if all(k.get(n)==v for n,v in want.items())),(-1,{}))
    if not re.search(r'^END$',log,re.M):bad.append('missing END')
    ton,on=find('TITLE on',cold='1');toff,off=find('TITLE off')
    imenu,menu=find('MENU ');icross,cross=find('SCRSHOT ',name='cold_cross',show='PRESS_START',pack='boot')
    intro_rows=rows('INTRO clip='); clips=[int(k['clip']) for i,k in intro_rows]
    if clips!=list(range(5)):bad.append('smoke logos/intro order is '+str(clips))
    if [int(fields(s)['clip']) for s in intro.splitlines() if s.startswith('INTRO clip=')]!=list(range(5)):bad.append('intro.txt missing original five clips')
    if ton<0 or toff<0:bad.append('missing cold title on/off')
    else:
        duration=float(off.get('shown','0'));notes.append('title shown %.2fs acceptedkey=%s demos=%s presses=%s'%(duration,off.get('key'),off.get('demos'),off.get('presses')))
        if duration<60:bad.append('title idle shorter than60s')
        if int(off.get('key','0'),0)!=8:bad.append('cold title accepted non-START key')
        if int(off.get('demos','-1'))!=0 or rows('DEMO '):bad.append('automatic demo occurred')
        if int(off.get('presses','0'))<2:bad.append('Cross/START input pair not evidenced')
        if not ton<icross<toff:bad.append('Cross did not retain title before accepted START')
    if len(intro_rows)==5:
        if not intro_rows[3][0]<ton<toff<intro_rows[4][0]<imenu:bad.append('logos/title/intro/room routing incorrect')
        for i,k in intro_rows:
            if int(k.get('err','-1')) or int(k.get('shown','0'))<=0 or int(k.get('audio','0'))<=0:bad.append('movie clip%s not played cleanly'%k.get('clip'))
        notes.append('movie clips=%s clip4shown=%s/audio=%s'%(clips,intro_rows[4][1].get('shown'),intro_rows[4][1].get('audio')))
    ish,sh=find('INTROSHOT ',name='cold_intro',clip='4')
    irs,rs=find('SHOT cold_room ')
    if not toff<ish<imenu<irs:bad.append('intro/room screenshot event order incorrect')
    scenario=(run/'scenario.txt').read_text()
    if not re.search(r'shot cold_idle\s+press cross\s+wait [\d.]+\s+shot cold_cross\s+press start',scenario):bad.append('scenario does not establish Cross then START at title')
    pulse=rows('TITLEPS ')
    if len(pulse)<30:bad.append('insufficient actual GU pulse rows')
    else:
        q=[k for i,k in pulse if k.get('cold')=='1' and k.get('irisbusy')=='0']
        if len(q)!=len(pulse):bad.append('early title draws obscured by iris or not cold')
        if len(q)>=30:
            t=np.array([float(k['t']) for k in q]);w=np.array([float(k['x1'])-float(k['x0']) for k in q])
            cx=np.array([(float(k['x1'])+float(k['x0']))/2 for k in q]);cy=np.array([(float(k['y1'])+float(k['y0']))/2 for k in q])
            p,ratio,peak=fit(t,w);early=w[t<=.13]
            if t[0]>.1 or len(early)<3:bad.append('missing first unmasked GU interval')
            elif early[0]>=peak*.985 or early[-1]<=early[0] or np.min(np.diff(early))<-.02:bad.append('first unmasked title pulse does not start belowpeak and grow')
            if abs(p-PS_P)>PS_P_TOL or abs(ratio-PS_R)>PS_R_TOL:bad.append('old period/amplitude bounds violated')
            if np.ptp(cx)>CENTER_TOL or np.ptp(cy)>CENTER_TOL:bad.append('old center bound violated')
            notes.append('first unmaskedGU t=%.4f first/peak=%.4f width=%.2f->%.2f period=%.3f min/max=%.4f'%(t[0],w[0]/peak,w[0],early[-1],p,ratio))
    images={}
    for name in ['cold_idle','cold_cross','cold_intro','cold_room']:
        p=run/(name+'.png')
        if not p.is_file():bad.append('missing image '+name);continue
        a=np.asarray(Image.open(p).convert('RGB')).astype(int);images[name]=a
        if a.shape!=(272,480,3):bad.append('wrong PSP framebuffer dimensions '+name)
    if len(images)==4 and all(a.shape==(272,480,3) for a in images.values()):
        for name in ['cold_idle','cold_cross']:
            q=images[name][215:249,130:350];n=int(((q[:,:,0]>170)&(q[:,:,1]>150)&(q[:,:,2]<130)).sum())
            if n<80:bad.append('no bright title prompt at '+name)
        delta=int(np.abs(images['cold_idle'][40:212,60:420]-images['cold_cross'][40:212,60:420]).max())
        if delta:bad.append('Cross changed static title logo region')
        if np.array_equal(images['cold_room'],images['cold_cross']) or np.array_equal(images['cold_intro'],images['cold_cross']):bad.append('intro/room capture stayed on title')
        notes.append('title logo Cross delta=%d; four native480x272 captures'%delta)
    return bad,notes

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('run',type=Path);ap.add_argument('--plants',action='store_true');a=ap.parse_args()
    log=(a.run/'smoke.txt').read_text();intro=(a.run/'intro.txt').read_text();bad,notes=check(a.run,log,intro)
    for n in notes:print(n)
    for b in bad:print('FAIL',b)
    print(('FAIL' if bad else 'PASS')+' cold-integration errors='+str(len(bad)))
    if a.plants:
        if bad:return 1
        plants={'demo':log.replace('TITLE off','DEMO on t=40\nTITLE off',1),
                'key':log.replace('TITLE off key=0x8','TITLE off key=0x4000',1),
                'iris':log.replace('irisbusy=0','irisbusy=1'),
                'shortidle':re.sub(r'(TITLE off[^\n]*shown=)[\d.]+',r'\g<1>59.0',log),
                'route':log.replace('INTRO clip=4','INTRO clip=3')}
        for name,text in plants.items():
            errors,_=check(a.run,text,intro);print('plant %s rejected=%s errors=%d'%(name,bool(errors),len(errors)))
            if not errors:return 1
        print('PASS five planted negatives')
    return int(bool(bad))
if __name__=='__main__':sys.exit(main())
