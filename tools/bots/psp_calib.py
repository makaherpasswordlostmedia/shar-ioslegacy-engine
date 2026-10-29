#!/usr/bin/env python3
"""Калибровка оценки кадра PSP по турам на железе (9D, 11A, 11B): cpu мс сцены = база уровня + k·ктреуг города + k·машины ИИ + взрыв + k·трафик.
  python3 tools/bots/psp_calib.py tools/bots/psp_calib.json"""
import re,glob,collections,statistics as st,json,sys
base='/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/psp-tour/'
rows=[]
for d in sorted(glob.glob(base+'*SHARTEST9D')+glob.glob(base+'*SHARTEST11A')+glob.glob(base+'*SHARTEST11B')+glob.glob(base+'*SHARTEST10B')+glob.glob(base+'*SHARTEST10')):
    tag=d.split('SHARTEST')[1]+d.split('/')[-1][:13]
    if not __import__('os').path.exists(d+'/smoke.txt'): continue
    cpu=collections.defaultdict(list); draw=collections.defaultdict(list); sec=collections.defaultdict(list)
    for ln in open(d+'/smoke.txt',errors='ignore'):
        p=ln.split()
        if ln.startswith('PHDRAW'):
            sc=re.search(r'scene=(\S+)',ln).group(1)
            m={k:(int(a),float(b)) for k,a,b,c in re.findall(r'(\w+)=(\d+)/([\d.]+)/(\d+)',ln)}
            draw[sc].append(m)
        elif ln.startswith('PHSEC'):
            sc=re.search(r'scene=(\S+)',ln).group(1); sec[sc].append({k:float(v) for k,v in re.findall(r'(\w+)=([\-\d.]+)',ln) if k!='t'})
        elif len(p)>=12 and re.match(r'^[\d.]+$',p[0]) and p[1] not in ('SCENE',) and re.match(r'^[\d.]+$',p[2]) and p[10]=='long' or (len(p)>=12 and re.match(r'^[\d.]+$',p[0]) and re.match(r'^[\d.]+$',p[5])):
            try:
                v=float(p[5])
                if v<200: cpu[p[1]].append(v)
            except: pass
    for sc in cpu:
        if sc not in draw or sc not in sec: continue
        n=min(len(cpu[sc]),len(draw[sc]))
        g=lambda k,i:st.median(x.get(k,(0,0))[i] for x in draw[sc])
        s=lambda k:st.median(x.get(k,0) for x in sec[sc])
        rows.append(dict(tour=tag,scene=sc,n=len(cpu[sc]),cpu=st.median(cpu[sc]),cpumax=max(cpu[sc]),build=s('build'),logic=st.median(x.get('ph1',0)+x.get('ph6',0)+x.get('ph7',0)+x.get('ph0',0)+x.get('ph2',0)+x.get('ph3',0)+x.get('ph4',0) for x in sec[sc]),
                         city_kt=g('city',1),props_kt=g('props',1),car3d_n=g('car3d',0),trf_n=g('trf',0),mcr_n=g('mcr',0),npc_n=g('npc',0),fx_kt=g('fx',1),x_trf=s('x_trf'),x_car3d=s('x_car3d'),x_mcr=s('x_mcr')))
import numpy as np
# (тур, сцена): число машин ИИ миссии, взрыв
AI={'P3_sr3':3,'P5_m6e2':2,'P5_m6e4':1,'L1_chase':1}
use=[]
for r in rows:
    sc=r['scene']
    if sc.endswith('load') or sc.startswith('C_') or sc in('start','L1_spawn') or r['cpu']>200: continue
    if sc in ('P4_m1e5','P6_bm1e5','P6_m2e1','P6_m7e1'): continue
    lv=int(sc[1]) if sc[0] in 'LP' else 0
    if lv in (0,4,6) or r['tour'].startswith('9D')==False and False: continue
    use.append((r,lv))
levels=sorted({lv for r,lv in use})
def feats(lv,kt,ai,boom,tr):
    return [1.0*(lv==L) for L in levels]+[kt,ai,boom,tr]
X=np.array([feats(lv,r['city_kt'],AI.get(r['scene'],0),1.0 if 'boom' in r['scene'] else 0.,r['trf_n']) for r,lv in use]); y=np.array([r['cpu'] for r,lv in use])
w,res,rk,sv=np.linalg.lstsq(X,y,rcond=None)
names=[f'base_L{L}' for L in levels]+['per_ktris','per_ai_car','boom','per_traffic_car']
errs=[]
for (r,lv),p in zip(use,X@w): errs.append(dict(tour=r['tour'][:5],scene=r['scene'],city_ktris=round(r['city_kt'],1),cpu=round(r['cpu'],1),model=round(float(p),1),err_pct=round(100*(float(p)-r['cpu'])/r['cpu'],1)))
E=[abs(e['err_pct']) for e in errs]
out=dict(coef=dict(zip(names,[round(float(x),3) for x in w])),mean_abs_err_pct=round(sum(E)/len(E),1),max_abs_err_pct=max(E),scenes=errs,source='psp-tour 9D, 11A, 11B (медианы по сцене)')
import json,sys
json.dump(out,open(sys.argv[1] if len(sys.argv)>1 else 'psp_calib.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out['coef'],ensure_ascii=False),out['mean_abs_err_pct'],out['max_abs_err_pct'])
