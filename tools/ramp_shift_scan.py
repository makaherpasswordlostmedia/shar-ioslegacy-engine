import numpy as np
def load(pt, psf, ff):
    port=np.loadtxt(pt)
    rows=[l.split('\t') for l in open(psf).read().splitlines()[1:]]
    ps=np.array([[float(r[9]),float(r[2]),float(r[6]),float(r[10])] for r in rows if int(r[0])>=ff])
    return port,ps
for name,pt,psf,ff in [('jz17','/Users/USER/Downloads/shar-psp-sonnet-walls-1015/build/_rep/twin_tr/jz17_k70.tsv','/Users/USER/Downloads/shar-psp/build/twins/o4/s_ps2_v99_jz17_70/jump.tsv',880),('jz16','/Users/USER/Downloads/shar-psp-sonnet-walls-1015/build/_rep/twin_tr/jz16_k70.tsv','/Users/USER/Downloads/shar-psp/build/twins/o4/s_ps2_v99_jz16_70/jump.tsv',1796)]:
    port,ps=load(pt,psf,ff)
    pa=port[:,4]; pvy=port[:,6]; ppit=port[:,8]
    xs=np.arange(-22,2,0.5)
    best=[]
    for d in np.arange(-3,4.1,0.5):
        # порт, сдвинутый на d вперёд: ходит раньше на d метров
        evy=[];epit=[]
        for x in xs:
            sv=np.interp(x,ps[:,0],ps[:,2]); sp=np.interp(x,ps[:,0],ps[:,3])
            pv=np.interp(x+d,pa,pvy); pp=np.interp(x+d,pa,ppit)
            evy.append((sv-pv)**2); epit.append((sp-pp)**2)
        best.append((d,np.sqrt(np.mean(evy)),np.sqrt(np.mean(epit))))
    print(name,'shift d  rmse_vy  rmse_pitch')
    for b in best: print('  %4.1f %6.2f %6.2f'%b)
