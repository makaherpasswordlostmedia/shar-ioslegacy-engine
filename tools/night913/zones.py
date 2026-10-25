# таблица зон №913 из ночных замеров: ячейка → 250 если видимая разница заметна и кадр с 250 в бюджете; 200 нет (формат хранит 0/1/2), иначе 150 (1); 130 (0) там, где разница 150↔250 незаметна и закрытая геометрия
# PSP-оценка = мс эмулятора × 4,6; бюджет: build150 ≤ 24 мс PSP и прирост build 150→250 ≤ 2,0 мс PSP (допущение, согласовать)
import json,struct,sys,os,collections
import numpy as np
J=os.environ.get('NIGHT913_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','build','night913'); J=os.path.abspath(J); os.chdir(J)   # рабочая папка: night913/sc, hz913, EBOOT; NIGHT913_DIR переопределяет
VIS=float(os.environ.get('VIS','0.05')); K=4.6; DMAX=2.0; B150MAX=24.0
P=json.load(open('night913/points.json')); cell=collections.defaultdict(list)
for p in P: cell[(p['L'],p['gx'],p['gz'])].append(p)
stat=collections.defaultdict(lambda: collections.Counter()); price=collections.defaultdict(list)
for L in range(1,8):
    b=bytearray(open(f'hz913/hzzone_l{L}.bin','rb').read()); w,h=struct.unpack_from('<II',b,4)
    for (l,gx,gz),ps in cell.items():
        if l!=L: continue
        ps=[p for p in ps if p['n250']>=p['n150']*1.05 or p['vis']<VIS]   # кадр считается, только если при 250 город реально рисуется дальше (иначе разница — туман/лента)
        if not ps: ps=cell[(l,gx,gz)]; ps=[dict(q,vis=0.) for q in ps]
        vis=max(p['vis'] for p in ps); d=max((p['b250']-p['b150'])*K for p in ps); c150=max(p['b150']*K for p in ps)
        old=b[24+gz*w+gx]
        if vis>=VIS: m=2 if (d<=DMAX and c150<=B150MAX) else 1
        else: m=0 if old==0 or vis<VIS/2 else 1
        b[24+gz*w+gx]=m; stat[L][m]+=1; price[L].append(sum(p['b150'] if m<2 else p['b250'] for p in ps)/len(ps)*K)
    open(f'night913/hzzone_l{L}.bin','wb').write(bytes(b))
for L in sorted(stat):
    t=sum(stat[L].values()); print(f"L{L}: клеток измерено {t}: 130 м {stat[L][0]}, 150 м {stat[L][1]}, 250 м {stat[L][2]}; средняя цена build по зонам {sum(price[L])/len(price[L]):.1f} мс PSP")
