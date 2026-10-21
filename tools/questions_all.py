#!/usr/bin/env python3
"""Сводный список вопросов к PS2 из всех рабочих копий (~/Downloads/shar-psp*/knowledge/questions.tsv).
Для каждого номера В — самая свежая по времени файла строка; помечает, в каких копиях вопрос есть и есть ли он у наблюдателя.
  python3 -I tools/questions_all.py  -> docs/handoff/ВОПРОСЫ_ВСЕ_КОПИИ.tsv"""
import glob,os,re,csv
D=os.path.expanduser('~/Downloads'); OBS='shar-psp-ps2-w'
best={}; where={}
for f in glob.glob(D+'/shar-psp*/knowledge/questions.tsv'):
    copy=f[len(D)+1:].split('/')[0]; mt=os.path.getmtime(f)
    for line in open(f,encoding='utf-8',errors='replace'):
        m=re.match(r'^(В\d+)\t',line)
        if not m: continue
        q=m.group(1); where.setdefault(q,set()).add(copy)
        if q not in best or mt>best[q][0]: best[q]=(mt,copy,line.rstrip('\n'))
rows=[['В','статус','у наблюдателя','свежая копия','все копии','текст']]
for q in sorted(best,key=lambda x:int(x[1:])):
    mt,copy,line=best[q]; parts=line.split('\t')
    st='отвечен' if re.search(r'отвечен|закрыт|решён',line) and not re.search(r'частично',line) else ('частично' if 'частично' in line else 'открыт')
    rows.append([q,st,'да' if OBS in where[q] else 'НЕТ',copy,' '.join(sorted(where[q])),'\t'.join(parts[1:])[:600]])
out=os.path.join(D,'shar-psp/docs/handoff/ВОПРОСЫ_ВСЕ_КОПИИ.tsv')
csv.writer(open(out,'w',newline=''),delimiter='\t').writerows(rows)
op=[r for r in rows[1:] if r[1]!='отвечен']
print(len(rows)-1,'вопросов; не отвечено',len(op),'; у наблюдателя нет:',' '.join(r[0] for r in op if r[2]=='НЕТ'))
