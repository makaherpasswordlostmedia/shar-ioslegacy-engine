#!/usr/bin/env python3
# №962: сравнение двух прогонов mem_l357.txt: куча свободна после загрузки L3/L5/L7 (последняя строка HEAPB сцены) и снимки m_l3/m_l5/m_l7.
# check.py НОВЫЙ СТАРЫЙ [--same-shots-only]   последняя строка PASS/FAIL. Пороги: выигрыш кучи L3 ≥ 1,0 МБ, L5 ≥ 1,0 МБ, L7 ≥ 1,5 МБ; снимки: средняя разница ≤ 3 из 255
import sys,re,os
from PIL import Image
import numpy as np
def heap(p):
    r={}
    for l in open(p,errors='ignore'):
        m=re.match(r'HEAPB t=([\d.]+) scene=(\S+) bytes=(\d+) blk=(\d+)',l)
        if m: r[m[2]]=(int(m[3]),int(m[4]))
    return r
def lva(p):
    r=[]
    for l in open(p,errors='ignore'):
        m=re.match(r'LVA level=(\d+) .* soft=(\d+) softmiss=(\d+) old=(\d)',l)
        if m: r.append((int(m[1]),int(m[2]),int(m[4])))
    return r
new,old=sys.argv[1],sys.argv[2]
hn,ho=heap(new+'/smoke.txt'),heap(old+'/smoke.txt'); ok=True
need={'M_L3':1.0,'M_L5':1.0,'M_L7':1.5}
for s,t in need.items():
    if s not in hn or s not in ho: print('нет сцены',s); ok=False; continue
    g=(hn[s][0]-ho[s][0])/1048576; b=(hn[s][1]-ho[s][1])/1048576
    print(f'{s}: куча свободна {hn[s][0]/1048576:.2f} против {ho[s][0]/1048576:.2f} МБ, выигрыш {g:+.2f} (нужно ≥ {t}), наибольший кусок {b:+.2f}')
    if g<t: ok=False
ln=lva(new+'/smoke.txt'); print('LVA нового:',ln)
if not any(x[0]==3 and x[1]>0 for x in ln): print('на L3 в запас ничего не легло'); ok=False
dm=0
for n in ('m_l3','m_l5','m_l7'):
    a=[f for f in os.listdir(new) if f.startswith(n) and f.endswith('.png')]; b=[f for f in os.listdir(old) if f.startswith(n) and f.endswith('.png')]
    if not a or not b: print('нет снимка',n); ok=False; continue
    A=np.asarray(Image.open(new+'/'+a[0]).convert('RGB'),dtype=float); B=np.asarray(Image.open(old+'/'+b[0]).convert('RGB'),dtype=float)
    d=float(np.abs(A-B).mean()); print(f'{n}: средняя разница {d:.2f}'); dm=max(dm,d)
if dm>3: ok=False
print('PASS' if ok else 'FAIL')
