import os,csv,re,json
R=os.path.expanduser('~/Downloads/shar-psp'); A=R+'/build/ps2ref/answers'; REC=R+'/build/ps2ref/recipes'
src=[]
for root in (R+'/knowledge/facts',os.path.expanduser('~/Downloads/shar-psp-ps2-w/knowledge/facts'),R+'/docs',R+'/tools/twins',R+'/knowledge/questions.tsv',os.path.expanduser('~/Downloads/shar-psp-ps2-w/docs/handoff')):
    if os.path.isfile(root): src.append((os.path.relpath(root,os.path.expanduser('~/Downloads')),open(root,errors='replace').read())); continue
    for dp,dn,fn in os.walk(root):
        dn[:]=[d for d in dn if d!='twins_library']
        for f in fn:
            if f.endswith(('.md','.yaml','.tsv','.json','.py')):
                try: src.append((os.path.relpath(os.path.join(dp,f),os.path.expanduser('~/Downloads')),open(os.path.join(dp,f),errors='replace').read()))
                except: pass
rows=[]
for d in sorted(os.listdir(A)):
    p=os.path.join(A,d)
    if not os.path.isdir(p): continue
    files=[]; size=0
    for dp,dn,fn in os.walk(p):
        for f in fn: files.append(f); size+=os.path.getsize(os.path.join(dp,f))
    ext={}; 
    for f in files: e=os.path.splitext(f)[1] or f; ext[e]=ext.get(e,0)+1
    rec=os.path.join(REC,d+'.json'); about=''
    if os.path.exists(rec):
        try:
            j=json.load(open(rec)); about=str(j.get('goal') or j.get('описание') or j.get('what') or j.get('question') or '')[:160]
        except: pass
    pat=re.compile(r'(?<![\w-])'+re.escape(d)+r'(?![\w-])'); refs=0; first=''; where=''
    for path,txt in src:
        ms=pat.findall(txt)
        if ms:
            refs+=len(ms)
            if not first:
                m=pat.search(txt); s=txt.rfind('\n',0,m.start())+1; e=txt.find('\n',m.end()); first=re.sub(r'\s+',' ',txt[s:e if e>0 else None])[:200]; where=path
    rows.append([d,round(size/2**20,1),len(files),' '.join(f'{k}×{v}' for k,v in sorted(ext.items(),key=lambda x:-x[1])[:5]),'да' if os.path.exists(rec) else '',about,refs,first,where])
H=['запись','МБ','файлов','типы файлов','рецепт','цель из рецепта','упоминаний','о чём (первое упоминание)','где']
csv.writer(open(R+'/knowledge/twins_library/ЗАПИСИ_PS2_answers.tsv','w',newline=''),delimiter='\t').writerows([H]+rows)
print(len(rows),'записей; без упоминаний:',sum(1 for r in rows if r[6]==0), [r[0] for r in rows if r[6]==0])
