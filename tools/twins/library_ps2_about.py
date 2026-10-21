import os,csv,re
R=os.path.expanduser('~/Downloads/shar-psp'); T=R+'/knowledge/twins_library/ЗАПИСИ_PS2_o4.tsv'
src=[]
for root in (R+'/tools/twins',R+'/knowledge',R+'/docs',os.path.expanduser('~/Downloads/shar-psp-ps2-w/knowledge/facts'),os.path.expanduser('~/Downloads/shar-psp-ps2-w/docs/handoff')):
    for dp,dn,fn in os.walk(root):
        dn[:]=[d for d in dn if d!='twins_library']
        for f in fn:
            if f.endswith(('.md','.yaml','.tsv','.json','.py')):
                try: src.append((os.path.relpath(os.path.join(dp,f),os.path.expanduser('~/Downloads')),open(os.path.join(dp,f),errors='replace').read()))
                except: pass
rows=list(csv.reader(open(T),delimiter='\t')); hdr=rows[0]+['о чём (первое упоминание)','где упомянуто']
out=[hdr]
for r in rows[1:]:
    name=r[0]; about=where=''
    pat=re.compile(r'(?<![\w-])'+re.escape(name)+r'(?![\w-])')
    for path,txt in src:
        m=pat.search(txt)
        if m:
            s=txt.rfind('\n',0,m.start())+1; e=txt.find('\n',m.end()); line=txt[s:e if e>0 else None].strip()
            about=re.sub(r'\s+',' ',line)[:220]; where=path; break
    out.append(r+[about,where])
csv.writer(open(T,'w',newline=''),delimiter='\t').writerows(out)
print('с описанием:',sum(1 for r in out[1:] if r[-1]),'из',len(out)-1)
