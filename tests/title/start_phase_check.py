#!/usr/bin/env python3
"""First PressStart grows below the peak; retain previous period/amplitude/center limits.
--source compiles actual ui.c psPulse and macros (NEW or --old), not a shadow formula.
RUN reads the actual-GU TITLEPS rectangles from the native emulator smoke log.
Midpoint is PORT_RULE. This gate does not assert exact PS2 phase/first-frame scale.
"""
import argparse, re, subprocess, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/title'))
from title_check import PS_P, PS_P_TOL, PS_R, PS_R_TOL, CENTER_TOL

def fit(t,w):
    best = None
    for p in np.arange(.3,1.2,.001):
        x = np.c_[np.ones_like(t),np.sin(2*np.pi*t/p),np.cos(2*np.pi*t/p)]
        c = np.linalg.lstsq(x,w,rcond=None)[0]; err = ((x@c-w)**2).mean()
        if best is None or err<best[0]: best = (err,p,c)
    err,p,c = best; amp = float(np.hypot(c[1],c[2]))
    return p,(c[0]-amp)/(c[0]+amp),float(c[0]+amp)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run',nargs='?');ap.add_argument('--source',action='store_true');ap.add_argument('--old',action='store_true')
    a=ap.parse_args();bad=[]
    if a.source:
        s=(ROOT/'viewer/ui.c').read_text();start=s.index('#ifndef TITLE_START_PHASE_OLD');end=s.index('// Правка Роба 412',start)
        actual=s[start:end];out=ROOT/'build/fe-title';out.mkdir(parents=True,exist_ok=True)
        c=out/'actual-pulse.c';exe=out/('source-old' if a.old else 'source-new')
        c.write_text('#include <math.h>\n#include <stdio.h>\n'+actual+'\nint main(void){for(int i=0;i<=60;i++){float t=i*.02f;printf("%.6f %.6f\\n",t,psPulse(t));}return 0;}\n')
        subprocess.run(['cc','-DTITLE_START_PHASE_OLD='+str(int(a.old)),str(c),'-lm','-o',str(exe)],check=True)
        r=np.array([[float(v) for v in ln.split()] for ln in subprocess.check_output([str(exe)],text=True).splitlines()])
        t,w=r[:,0],r[:,1];cx=cy=np.zeros_like(t);kind='actual ui.c '+('OLD' if a.old else 'NEW')
    else:
        if not a.run:ap.error('RUN or --source required')
        run=Path(a.run);log=(run/'smoke.txt').read_text();kind='actual GU '+run.name
        if not re.search(r'^END$',log,re.M):bad.append('missing END')
        if not re.search(r'^TITLE on',log,re.M):bad.append('missing real title entry')
        rows=[tuple(float(v) for v in re.findall(r'=(-?[\d.]+)',l)) for l in log.splitlines() if l.startswith('TITLEPS ')]
        if len(rows)<30:print('FAIL insufficient TITLEPS rows');return 1
        r=np.array(rows);t=r[:,0];w=r[:,3]-r[:,1];cx=(r[:,1]+r[:,3])/2;cy=(r[:,2]+r[:,4])/2
    p,ratio,peak=fit(t,w)
    early=w[t<=.13];lastt=float(t[t<=.13][-1]) if len(early) else -1
    if t[0]>.10:bad.append('missing early frame: t0=%.4f'%t[0])
    if len(early)<3:bad.append('insufficient early frames')
    else:
        if early[0]>=peak*.985:bad.append('first frame starts at peak: %.4f'%(early[0]/peak))
        if early[-1]<=early[0] or np.min(np.diff(early))<-.02:bad.append('initial size does not grow')
    if abs(p-PS_P)>PS_P_TOL:bad.append('period changed: %.3f'%p)
    if abs(ratio-PS_R)>PS_R_TOL:bad.append('amplitude changed: %.3f'%ratio)
    if np.ptp(cx)>CENTER_TOL or np.ptp(cy)>CENTER_TOL:bad.append('center moved')
    print('%s: t0=%.4f first/peak=%.4f early_end_t=%.4f first/end=%.4f/%.4f period=%.3f min/max=%.4f center_span=%.4f/%.4f' %
          (kind,t[0],w[0]/peak,lastt,w[0],early[-1] if len(early) else -1,p,ratio,np.ptp(cx),np.ptp(cy)))
    for b in bad:print('FAIL',b)
    print(('FAIL' if bad else 'PASS')+' first-title-phase errors='+str(len(bad)))
    return int(bool(bad))
if __name__=='__main__':sys.exit(main())
