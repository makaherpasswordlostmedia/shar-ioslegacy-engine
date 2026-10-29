# №912: внешний ободок туши контура машин — потерян ли хоть один пиксель между двумя сборками (проверка любой правки контура, tests/toon/rim912).
# Сценарии own.txt (своя машина L1, 10 ракурсов) и trf.txt (три модели трафика, 6 ракурсов) снимают каждый ракурс дважды: обычный кадр и «ключ» (flag lumakey 1 — машина и Гомер сплошным цветом, маска силуэта).
# Запуск: оба сценария безголовым эмулятором на двух EBOOT (прежний и новый), снимки в папки OLD и NEW; затем
#   python3 rim912.py OLD NEW f b l r hf hb n1 n2 far top      и      python3 rim912.py OLD NEW t0_0 t0_1 ... t2_5 --red ДИР_красной_сборки
# Слепые кадры t1_0 и t2_0 (у первого ракурса фургона и автобуса ключ не успевает примениться: маска пустая; прогрев ключа и отодвинутая камера не помогли) в список не включать — гейт их и так назовёт ошибкой
# Внешний ободок = тёмные пиксели (яркость < 70) снаружи маски в пределах 5 px от неё, кроме правой части с радаром; потеряно = были у прежней сборки и пропали у новой. Допуск — RIM_TOL (0,05 %) пикселей ободка (один пиксель из 27 тысяч — шум дизеринга, не потеря). Код выхода 1, если потеряно больше допуска; 2 — кадр с пустой маской (гейт слеп); 3 — красный контроль не покраснел.
# Красный контроль встроен: на тех же кадрах у новой сборки стираются 1 % пикселей ободка (каждый сотый по растру) — гейт обязан это поймать; необязательный ключ --red ДИР добавляет внешний (например, сборка NPC_CAR_TOON_OLD=1, 419 потерь) — она тоже обязана покраснеть.
import sys, numpy as np
RIM_TOL = 0.0005
from PIL import Image
def load(p): return np.array(Image.open(p).convert('RGB')).astype(int)
def mask_of(k):
    r,g,b=k[:,:,0],k[:,:,1],k[:,:,2]
    return ((r>230)&(g<40)&(b>230))|((g>230)&(r<40)&(b<40))
def dil(m,n):
    out=m.copy()
    for dy in range(-n,n+1):
        for dx in range(-n,n+1):
            out|=np.roll(np.roll(m,dy,0),dx,1)
    return out
def run(od,nd,names,rad=5,thr=70,quiet=False):
    tl=tg=tn=0; empty=[]; red=0
    for n in names:
        o=load(f'{od}/{n}.png'); w=load(f'{nd}/{n}.png'); k=load(f'{od}/{n}k.png')
        m=mask_of(k); m[:50]=False
        if not m.any(): empty.append(n)
        near=dil(m,rad)&~m; near[:50]=False; near[:,380:]=False
        do=(o.sum(2)/3<thr); dn=(w.sum(2)/3<thr)
        ro=do&near; rn=dn&near
        lost=int((ro&~dn).sum()); gain=int((rn&~do).sum())
        idx=np.flatnonzero(ro.ravel()); dn2=dn.copy().ravel(); dn2[idx[::100]]=False   # красный контроль: стёрт каждый сотый пиксель ободка
        red+=int((ro.ravel()&~dn2).sum())
        tl+=lost; tg+=gain; tn+=int(ro.sum())
        if not quiet: print('%-6s внешний ободок: старый %5d  потеряно %3d  добавлено %3d  маска %6d%s'%(n,ro.sum(),lost,gain,m.sum(),'  ПУСТАЯ МАСКА' if not m.any() else ''))
    return tl,tg,tn,empty,red
def main():
    a=sys.argv[1:]; reds=[]
    while '--red' in a: i=a.index('--red'); reds.append(a[i+1]); del a[i:i+2]
    od,nd,names=a[0],a[1],a[2:]
    tl,tg,tn,empty,red=run(od,nd,names)
    print('ИТОГО ободок старый %d, потеряно %d (%.3f %%, допуск %.3f %%), добавлено %d'%(tn,tl,100*tl/max(1,tn),100*RIM_TOL,tg))
    if empty: print('ОШИБКА: пустая маска (гейт слеп) в кадрах: '+' '.join(empty)); sys.exit(2)
    print('красный контроль (стёрт каждый сотый пиксель): потеряно %d из %d -> %s'%(red,tn,'красный как надо' if red>RIM_TOL*tn else 'НЕ КРАСНЫЙ'))
    if not red>RIM_TOL*tn: sys.exit(3)
    for r in reds:
        import os; rn=[n for n in names if os.path.exists(f'{r}/{n}.png')]   # красная папка может хранить не все кадры (только трафик)
        l2=run(od,r,rn,quiet=True)[0]; ok=l2>RIM_TOL*tn
        print('внешний красный контроль %s: потеряно %d -> %s'%(r,l2,'красный как надо' if ok else 'НЕ КРАСНЫЙ'))
        if not ok: sys.exit(3)
    sys.exit(1 if tl>RIM_TOL*tn else 0)
main()
