import numpy as np
def sinc(x): return np.sinc(x)
def lanczos(x,a=3): return np.where(np.abs(x)<a, sinc(x)*sinc(x/a), 0.0)
def kaiser(x,a=3,beta=4.0):
    t=np.clip(1-(x/a)**2,0,1); return np.where(np.abs(x)<a, sinc(x)*np.i0(beta*np.sqrt(t))/np.i0(beta), 0.0)
def box(x): return np.where(np.abs(x)<=0.5,1.0,0.0)
def resp(kern,scale,f):
    # source signal cos(2 pi f n), downsample by `scale` (2): output sample at center position 0: y = sum w(n/scale) x[n] / sum w
    n=np.arange(-int(8*scale),int(8*scale)+1); w=kern(n/scale); w=w/w.sum()
    # amplitude of output = |sum w cos(2 pi f n)| (phase 0 is worst/most informative as cos); also sin
    return np.hypot((w*np.cos(2*np.pi*f*n)).sum(),(w*np.sin(2*np.pi*f*n)).sum())
scale=2.0
cands=[('box',box),('lanczos3',lambda x:lanczos(x,3)),('lanczos2',lambda x:lanczos(x,2))]+[(f'kaiser a3 b{b}',(lambda b:lambda x:kaiser(x,3,b))(b)) for b in (2,3,4,6)]+[('kaiser a4 b4',lambda x:kaiser(x,4,4.0))]
print('фильтр | усиление на f=0,10 (проход, 1=как есть) | f=0,20 (середина) | утечка в алиас f=0,35 | f=0,45 | f=0,5 (Найквист исх.) | перелёт ступени (%)')
for name,k in cands:
    n=np.arange(-20,21); w=k(n/scale); w=w/w.sum(); step=np.cumsum(w[::-1])[::-1]  # step response overshoot
    st=np.cumsum(w); over=(st.max()-1)*100
    print(f'{name:14s} | {resp(k,scale,.10):.3f} | {resp(k,scale,.20):.3f} | {resp(k,scale,.35):.3f} | {resp(k,scale,.45):.3f} | {resp(k,scale,.5):.3f} | {over:.1f}')
