import os,sys,re,hashlib,time,shutil,csv
RUNS=os.path.expanduser('~/Downloads/shar-psp/build/twins/scen/full')
LIB=sys.argv[1]; DIST=sys.argv[2]
os.makedirs(LIB,exist_ok=True); os.makedirs(DIST,exist_ok=True)
OUTEXT={'.txt','.log','.tsv','.json','.md','.png','.csv'}
rows=[]; scen={}
for d in sorted(os.listdir(RUNS)):
    p=os.path.join(RUNS,d)
    if not os.path.isdir(p): continue
    st=os.stat(p); date=time.strftime('%Y-%m-%d %H:%M',time.localtime(st.st_mtime))
    sc=open(os.path.join(p,'scenario.txt'),errors='replace').read() if os.path.exists(os.path.join(p,'scenario.txt')) else ''
    lv=re.findall(r'^flag level (\d)',sc,re.M); scenes=re.findall(r'^scene (\S+)',sc,re.M); shots=re.findall(r'^shot (\S+)',sc,re.M)
    eb=os.path.join(p,'EBOOT.PBP'); ebh=hashlib.sha256(open(eb,'rb').read()).hexdigest()[:8] if os.path.exists(eb) else ''
    sm=open(os.path.join(p,'smoke.txt'),errors='replace').read() if os.path.exists(os.path.join(p,'smoke.txt')) else ''
    stats=re.findall(r'^STAT (\S+) frames (\d+) p95 ([\d.]+).*?missed (\d+).*?allocfail (\d+).*?memfail (\d+)',sm,re.M)
    end='END' in sm
    bb=os.path.join(p,'blackbox.txt'); stall=('STALL' in open(bb,errors='replace').read()) if os.path.exists(bb) else ''
    sh=''
    if sc.strip():
        sh=hashlib.sha1(sc.encode()).hexdigest()[:10]
        if sh not in scen: scen[sh]=(d,sc,lv,scenes)
    worst=max((float(s[2]) for s in stats),default='')
    rows.append([d,date,ebh,','.join(sorted(set(lv))),','.join(dict.fromkeys(scenes))[:80],len(shots),len(stats),worst,sum(int(s[3]) for s in stats),sum(int(s[4])+int(s[5]) for s in stats),'да' if end else 'нет',stall,sh])
    # результаты — в сейф
    for dp,dn,fn in os.walk(p):
        for f in fn:
            e=os.path.splitext(f)[1].lower(); src=os.path.join(dp,f); rel=os.path.relpath(src,p)
            if e in OUTEXT or f in ('smokelog','ballast'):
                dst=os.path.join(DIST,d,rel); os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy2(src,dst)
            elif e=='.bmp':
                png=os.path.splitext(src)[0]+'.png'
                if not os.path.exists(png):
                    dst=os.path.join(DIST,d,os.path.splitext(rel)[0]+'.png'); os.makedirs(os.path.dirname(dst),exist_ok=True)
                    os.system(f'sips -s format png "{src}" --out "{dst}" >/dev/null 2>&1')
with open(os.path.join(LIB,'КАТАЛОГ_ПРОГОНОВ.tsv'),'w',newline='') as f:
    w=csv.writer(f,delimiter='\t'); w.writerow(['прогон','дата','EBOOT','уровни','сцены','снимков','STAT','худший p95 мс','пропуски','ошибки памяти','дошёл до END','STALL в ящике','сценарий'])
    w.writerows(rows)
sd=os.path.join(LIB,'сценарии'); os.makedirs(sd,exist_ok=True)
with open(os.path.join(LIB,'СЦЕНАРИИ.tsv'),'w',newline='') as f:
    w=csv.writer(f,delimiter='\t'); w.writerow(['сценарий','первый прогон','уровни','сцены','прогонов с ним'])
    cnt={}
    for r in rows: cnt[r[-1]]=cnt.get(r[-1],0)+1
    for sh,(d,sc,lv,scenes) in sorted(scen.items(),key=lambda x:x[1][0]):
        open(os.path.join(sd,f'{d}__{sh}.txt'),'w').write(sc)
        w.writerow([sh,d,','.join(sorted(set(lv))),','.join(dict.fromkeys(scenes))[:80],cnt.get(sh,0)])
print('прогонов',len(rows),'уникальных сценариев',len(scen))
