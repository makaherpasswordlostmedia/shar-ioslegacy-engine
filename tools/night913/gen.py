# ночной прогон №913: сценарии-куски по ячейкам зон; точка = центр ячейки; кадры при дали 150 и 250
# ячейки класса 150/250 (кандидаты) — 4 курса, ячейки класса 130 — 1 курс (по номеру ячейки, чтобы смотреть в разные стороны)
import sys,struct,math,os
outd='night913/sc'; os.makedirs(outd,exist_ok=True); CH=100
for L in range(1,8):
    b=open(f'hz913/hzzone_l{L}.bin','rb').read(); w,h=struct.unpack_from('<II',b,4); x0,z0,st=struct.unpack_from('<fff',b,12)
    pts=[]
    for gz in range(h):
        for gx in range(w):
            m=b[24+gz*w+gx]
            if m==255: continue
            ks=[0,1,2,3] if m in(1,2) else [(gx*7+gz*3)%4]
            for k in ks: pts.append((gx,gz,k,m))
    for ci in range(0,len(pts),CH):
        s=["wait 12","scene LOAD",f"flag golevel {L}","wait 40","flag cfgdefaults 1","flag far150 0","flag drawdist 60","press triangle 0.2","wait 3"]
        for gx,gz,k,m in pts[ci:ci+CH]:
            x=x0+(gx+.5)*st; z=z0+(gz+.5)*st; c=2*math.pi*k/4
            n=f"{gx}_{gz}_{k}"
            s+=[f"foot {x:.0f} {z:.0f} {c:.3f}","flag drawdist 60","wait 1.5",f"scene a_{n}","wait 0.8",f"shot a_{n}","flag drawdist 100","wait 1.2",f"scene b_{n}","wait 0.8",f"shot b_{n}"]
        s.append("end"); open(f'{outd}/L{L}_{ci//CH:02d}.txt','w').write("\n".join(s)+"\n")
    print(L,len(pts),'точек',(len(pts)+CH-1)//CH,'кусков')
