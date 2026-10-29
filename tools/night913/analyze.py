# разбор ночного прогона №913: на точку — видимая разница (доля пикселей верхней половины кадра с разницей >30 между даль 150 и 250) и цена (build, x_city, вызовы, мс эмулятора; ×4,6 → PSP)
import sys,glob,os,re,json,collections
import numpy as np
from PIL import Image
J=os.environ.get('NIGHT913_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','build','night913'); J=os.path.abspath(J); os.chdir(J)   # рабочая папка: night913/sc, hz913, EBOOT; NIGHT913_DIR переопределяет
med=lambda x: sorted(x)[len(x)//2] if x else float('nan')
res=[]
for d in sorted(glob.glob('out_NL*_*')):
    if not os.path.exists(d+'/DONE'): continue
    L=int(re.match(r'out_NL(\d+)_',d).group(1)); sc=None; D=collections.defaultdict(lambda: collections.defaultdict(list))
    for l in open(d+'/smoke.txt'):
        if l.startswith('SCENE '): sc=l.split()[1]; continue
        k=l.split(' ',1)[0]
        if sc and k in('PHSEC','RFAST'):
            for a,v in re.findall(r'(\w+)=(-?[\d.]+)',l): D[sc][a].append(float(v))
    for s in [s for s in D if s.startswith('a_')]:
        n=s[2:]; b='b_'+n; ia,ib=f'{d}/a_{n}.png',f'{d}/b_{n}.png'
        if b not in D or not os.path.exists(ia) or not os.path.exists(ib): continue
        A=np.array(Image.open(ia).convert('RGB')).astype(int); B=np.array(Image.open(ib).convert('RGB')).astype(int)
        top=np.abs(A-B).max(2)[50:136]; vis=float((top>30).mean())
        gx,gz,k=map(int,n.split('_'))
        g=lambda sc_,a: med(D[sc_][a])
        res.append(dict(L=L,gx=gx,gz=gz,k=k,vis=vis,b150=g(s,'build'),b250=g(b,'build'),c150=g(s,'x_city'),c250=g(b,'x_city'),n150=g(s,'draws'),n250=g(b,'draws')))
json.dump(res,open('night913/points.json','w'))
print(len(res),'точек')
