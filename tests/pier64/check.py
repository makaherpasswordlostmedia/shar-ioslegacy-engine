#!/usr/bin/env python3
# №957б: сравнение двух прогонов arch.txt. Журнал GQ944: квады свечения предметов (site=coll/bonus/props), ставшие бликом, размер sc = бо́льшая сторона × 0,7.
# check.py НОВЫЙ СТАРЫЙ   последняя строка PASS/FAIL. Новый: на всех уровнях нет блика крупнее sc 2,1 (сторона 3 м) от предметов и бонус-игр; старый: на L6 есть;
# снимки арок L6 новый против старого различаются, сцены L1…L7 и в новом и в старом дошли (по HEAPB сцены A_L*)
import sys,re,os
from PIL import Image
import numpy as np
def big(p):
    r={}
    for l in open(p,errors='ignore'):
        m=re.match(r'GQ944 lv=(\d+) site=(\w+) p=(\S+) sc=([\d.]+) ',l)
        if m and m[2] in('coll','bonus') and float(m[4])>2.1: r.setdefault(int(m[1]),[]).append((m[3],float(m[4])))
    return r
def scenes(p):
    s=set()
    for l in open(p,errors='ignore'):
        m=re.match(r'HEAPB t=\S+ scene=(A_L\d)',l)
        if m: s.add(m[1])
    return s
new,old=sys.argv[1],sys.argv[2]; ok=True
bn,bo=big(new+'/smoke.txt'),big(old+'/smoke.txt')
print('крупные блики новый:',bn); print('крупные блики старый:',bo)
if bn: print('в новом остались крупные блики предметов'); ok=False
if not bo.get(6): print('в старом на L6 нет крупного блика — проверять нечего'); ok=False
for tag,pth in (('новый',new),('старый',old)):
    miss=sorted({'A_L%d'%i for i in range(1,8)}-scenes(pth+'/smoke.txt'))
    if miss: print(tag,'нет сцен',miss); ok=False
dm=[]
for n in ('a6_arch1','a6_arch1b','a6_arch2','a6_arch3'):
    a=[f for f in os.listdir(new) if f.startswith(n) and f.endswith('.png')]; b=[f for f in os.listdir(old) if f.startswith(n) and f.endswith('.png')]
    if not a or not b: print('нет снимка',n); ok=False; continue
    A=np.asarray(Image.open(new+'/'+a[0]).convert('RGB'),dtype=float); B=np.asarray(Image.open(old+'/'+b[0]).convert('RGB'),dtype=float)
    d=np.abs(A-B).sum(axis=2); dm.append((n,int((d>40).sum()))); print(n,'пикселей с разницей >40:',int((d>40).sum()))
if not any(c>=30 for n,c in dm if n in('a6_arch1','a6_arch1b','a6_arch2')): print('снимки арок не различаются (блик не виден)'); ok=False
print('PASS' if ok else 'FAIL')
