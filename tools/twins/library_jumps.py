import os,csv,math,collections
O=os.path.expanduser('~/Downloads/shar-psp/build/twins/o4')
out=[]
for d in sorted(os.listdir(O)):
    f=os.path.join(O,d,'jump.tsv')
    if not os.path.exists(f): continue
    R=[r for r in csv.DictReader(open(f,encoding='utf-8',errors='replace'),delimiter='\t')]
    if len(R)<10: out.append([d,len(R)]+['']*9); continue
    ph=collections.Counter(r['фаза'] for r in R)
    fly=[i for i,r in enumerate(R) if r['фаза'].strip()=='полёт']
    if not fly: out.append([d,len(R),'НЕ ДОЕХАЛ до разгона']+['']*8); continue
    i0=fly[0]; y=[float(r['y']) for r in R]; v=[float(r['v']) for r in R]
    # отрыв: первый кадр фазы не «дорога»; дальше ищем посадку — минимум y после пика, затем стабилизация
    seg=range(i0,len(R)); ipk=max(seg,key=lambda i:y[i])
    # посадка: первый кадр после пика, где y перестал падать (vy>=0) — по разности
    il=next((i for i in range(ipk+1,len(R)-1) if y[i+1]-y[i]>=-0.005),len(R)-1)
    fr=lambda i:int(R[i]['кадр'])
    air=(fr(il)-fr(i0))/50.0
    dist=math.hypot(float(R[il]['x'])-float(R[i0]['x']),float(R[il]['z'])-float(R[i0]['z']))
    vl=v[il]; v1=v[min(len(R)-1,il+25)]  # через 0,5 с
    # отскок: максимум y в 1 с после посадки минус y посадки
    after=range(il,min(len(R),il+50)); bounce=max(y[i] for i in after)-y[il]
    out.append([d,len(R),'/'.join(f'{k}:{n}' for k,n in ph.items()),round(v[i0]*3.6,1),round(y[ipk]-y[i0],2),round(air,2),round(dist,1),round(vl*3.6,1),round(v1*3.6,1),round(bounce,2),f"{R[i0]['x']},{R[i0]['z']}"])
H=['запись','строк','фазы','км/ч на отрыве','высота над отрывом м','в воздухе с','дальность м','км/ч в посадке','км/ч через 0,5 с','подскок после посадки м','точка отрыва x,z']
p=os.path.expanduser('~/Downloads/shar-psp/knowledge/twins_library/ПРЫЖКИ_PS2_o4.tsv')
csv.writer(open(p,'w',newline=''),delimiter='\t').writerows([H]+out)
for r in [H]+out[:8]: print('\t'.join(map(str,r)))
print('всего',len(out))
