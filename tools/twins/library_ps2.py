import os,csv,re,subprocess
R=os.path.expanduser('~/Downloads/shar-psp'); O=R+'/build/twins/o4'
facts=''
for root in (R+'/knowledge/facts',os.path.expanduser('~/Downloads/shar-psp-ps2-w/knowledge/facts'),R+'/docs/handoff',R+'/tools/twins'):
    for dp,dn,fn in os.walk(root):
        for f in fn:
            try: facts+=open(os.path.join(dp,f),errors='replace').read()
            except: pass
rows=[]
for d in sorted(os.listdir(O)):
    p=os.path.join(O,d)
    if not os.path.isdir(p): continue
    t=os.path.join(p,'t.tsv'); n=sum(1 for _ in open(t,errors='replace'))-1 if os.path.exists(t) else 0
    first=last=''
    if n>0:
        L=open(t,errors='replace').read().split('\n'); hdr=L[0].split('\t'); a=L[1].split('\t'); b=[x for x in L if x.strip()][-1].split('\t')
        def g(r,k): 
            try: return r[hdr.index(k)]
            except: return ''
        first=f"{g(a,'x')},{g(a,'z')}"; last=f"{g(b,'x')},{g(b,'z')} v={g(b,'v')}"
        lastframe=g(b,'кадр')
    else: lastframe=''
    png=len(os.listdir(os.path.join(p,'png'))) if os.path.isdir(os.path.join(p,'png')) else 0
    wav='да' if any(f.endswith('.wav') for f in os.listdir(p)) else ''
    sc=open(os.path.join(p,'script.txt'),errors='replace').read() if os.path.exists(os.path.join(p,'script.txt')) else ''
    acts=' '.join(re.findall(r'^\d+ (\w+)',sc,re.M)[:8])
    refs=len(re.findall(re.escape('o4/'+d)+r'\b',facts))+len(re.findall(r'\b'+re.escape(d)+r'\b',facts))
    rows.append([d,lastframe,first,last,png,wav,acts,refs])
os.makedirs(R+'/knowledge/twins_library',exist_ok=True)
with open(R+'/knowledge/twins_library/ЗАПИСИ_PS2_o4.tsv','w',newline='') as f:
    w=csv.writer(f,delimiter='\t'); w.writerow(['запись','последний кадр','старт x,z','конец x,z и скорость','кадров png','звук','команды скрипта','упоминаний в фактах/доках'])
    w.writerows(rows)
print(len(rows),'записей; без упоминаний:',sum(1 for r in rows if r[-1]==0))
