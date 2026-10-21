#!/usr/bin/env python3
"""Offline map, measured candidates and explicit coverage of Rob's anchor cells."""
import argparse, base64, collections, html, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from col_check import load,parse_col
X0=Z0=-700.;CELL=100.;COLS,ROWS=12,15;LET='ABCDEFGHJKLM'
COLOR={'прозрачная':'#dc3529','дыра':'#9c4378','ступень':'#ab791a','бордюр':'#e28613','несбиваемое':'#1979a9','куст':'#357b45','анимация':'#0b918d','видимая':'#8a8a83','граница':'#8a8a83','разрешённая':'#8a8a83','край':'#8a8a83','edge32':'#ab791a','push1':'#ab791a'}
HIDDEN={'видимая','граница','разрешённая','край'}
def code(x,z):
 fx,fz=(x-X0)/CELL,(z-Z0)/CELL;c,r=int(np.floor(fx)),int(np.floor(fz))
 if not(0<=c<COLS and 0<=r<ROWS):return '--'
 return f'{LET[c]}{r+1}-{1+min(2,int((fx-c)*3))+3*min(2,int((fz-r)*3))}'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('level');ap.add_argument('run');ap.add_argument('--title',default='');ap.add_argument('--px',type=float,default=1);a=ap.parse_args();run=Path(a.run);res=json.loads((run/'walls.json').read_text());b,L=load(a.level);C=parse_col(b,L['col']);T=C['tri']
 xmin,xmax=T[:,:3,0].min()-20,T[:,:3,0].max()+20;zmin,zmax=T[:,:3,2].min()-20,T[:,:3,2].max()+20;s=a.px;W,H=int((xmax-xmin)*s),int((zmax-zmin)*s)
 img=Image.new('RGB',(W,H),(233,232,224));d=ImageDraw.Draw(img);P=lambda x,z:((x-xmin)*s,(z-zmin)*s);ys=T[:,:3,1].mean(1);lo,hi=np.percentile(ys,[2,98])
 for t,y in zip(T,ys):
  g=int(155+55*np.clip((y-lo)/(hi-lo+1e-6),0,1));d.polygon([P(t[k,0],t[k,2]) for k in range(3)],fill=(g,g,g-5))
 for c in range(COLS+1):d.line([P(X0+c*CELL,zmin),P(X0+c*CELL,zmax)],fill=(130,130,125))
 for r in range(ROWS+1):d.line([P(xmin,Z0+r*CELL),P(xmax,Z0+r*CELL)],fill=(130,130,125))
 for c in range(COLS):
  for r in range(ROWS):
   u,v=P(X0+c*CELL+3,Z0+r*CELL+3)
   if 0<=u<W and 0<=v<H:d.text((u,v),f'{LET[c]}{r+1}',fill=(35,35,35))
 img.save(run/'map.png');dots=[];rows=[];anchors=[]
 for n,c in enumerate(res['clusters']):
  fam=c['family'];color=COLOR.get(fam,'#777770');u,v=P(c['x'],c['z']);place=code(c['x'],c['z']);source=str(c.get('source',''));origin=c.get('origin','');q=html.escape(f'{place} {source} {fam}',quote=True);f=html.escape(fam,quote=True)
  evidence=c.get('samples',[c.get('evidence',{})]);ev=html.escape(json.dumps(evidence,ensure_ascii=False,indent=1));rep=html.escape(c.get('repro',''))
  dots.append(f'<circle class="obs" data-f="{f}" data-q="{q}" data-id="r{n}" cx="{u:.1f}" cy="{v:.1f}" r="4" fill="{color}" stroke="white" stroke-width=".7"><title>{q}</title></circle>')
  rows.append(f'<tr class="obs" data-f="{f}" data-q="{q}" id="r{n}"><td>{place}</td><td style="color:{color}">{f}</td><td>{html.escape(source)}</td><td>{html.escape(origin)}</td><td>{c.get("n",1)}</td><td>{c["x"]:.2f}; {c["z"]:.2f}<details><summary>Измерение и повтор</summary><pre>{ev}</pre><code>{rep}</code></details></td></tr>')
 for c in res.get('anchors',[]):
  matching=[r for r in res['clusters'] if code(r['x'],r['z'])==c];bad=[r for r in matching if r['family'] not in HIDDEN]
  anchors.append(f'<li><b>{c}</b>: {len(bad)} кандидатов, {len(matching)-len(bad)} видимых/разрешённых; '+('есть измеренные упоры' if bad else 'дефект этим прогоном не подтверждён, не считать исправленным')+'</li>')
  col=LET.index(c[0]);rr,sub=map(int,c[1:].split('-'));x=X0+col*100+(sub-1)%3*100/3;z=Z0+(rr-1)*100+(sub-1)//3*100/3;u,v=P(x,z)
  dots.append(f'<rect x="{u}" y="{v}" width="{100*s/3}" height="{100*s/3}" fill="none" stroke="#a46a00" stroke-width="2" stroke-dasharray="4 3"><title>Точка Роба {c}</title></rect>')
 if res.get('level')==1:anchors.append('<li>Стадион L1: проверены все экземпляры гидрантов из данных; точная клетка замечания не задана. Ищите hydr в таблице/props.jsonl</li>')
 for note in res.get('anchorReview',[]):anchors.append('<li>'+html.escape(note)+'</li>')
 families=collections.Counter(c['family'] for c in res['clusters']);controls=' '.join(f'<label><input type="checkbox" value="{html.escape(f)}" {"" if f in HIDDEN else "checked"}> <span style="color:{COLOR.get(f,"#777770")}">{html.escape(f)} ({n})</span></label>' for f,n in families.items())
 bg=base64.b64encode((run/'map.png').read_bytes()).decode();coverage=html.escape(json.dumps(res.get('coverage',{}),ensure_ascii=False,indent=2));title=html.escape(a.title)
 (run/'report.html').write_text(f'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{title} · препятствия</title>
<style>body{{font:14px system-ui;background:#f6f5f2;color:#1a1a1a;margin:24px}}h1{{font-size:24px}}label{{display:inline-block;margin:5px 14px 5px 0}}input[type=search]{{padding:8px;width:min(95%,420px)}}svg{{width:100%;min-width:700px}}.map{{overflow:auto;max-height:75vh;background:#ddd}}circle{{cursor:pointer}}table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;text-align:left;border-bottom:1px solid #d5d4cd;vertical-align:top}}tr:target{{background:#fff0b5}}pre{{white-space:pre-wrap;max-width:600px}}code{{word-break:break-all}}.off{{display:none}}summary{{cursor:pointer}}.bar{{position:sticky;top:0;background:#f6f5f2;padding:8px 0;z-index:2}}</style>
<a href="../index.html">Все уровни</a><h1>{title} · всё, обо что ударяешься</h1><p>{html.escape(res.get('scope','CPU-измерения; кандидаты требуют разбора'))}</p>
<p>{res.get('km',0):.1f} км случайного роя; {res.get('carSeconds',0)/3600:.1f} машино-часов. Прицельные заезды идут отдельно; клик по точке открывает строку. Дома, границы и изгороди №421 серые, скрыты по умолчанию</p>
<div class="bar"><input type="search" placeholder="Клетка или объект, например D7-6, crane, hydr" aria-label="Поиск"><div>{controls}</div></div><div class="map"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Карта препятствий {title}"><image href="data:image/png;base64,{bg}" width="{W}" height="{H}"/>{''.join(dots)}</svg></div>
<h2>Замечания Роба</h2><ul>{''.join(anchors)}</ul><details><summary>Покрытие детекторов и входные данные</summary><pre>{coverage}</pre><p>SHA256 уровня: {res.get('levelSha','')}</p><p>Анимации: пять поз клипа ANM1, коллизия и рисунок в одной позе; мгновенные события между позами не покрыты. Нет контакта означает пробел покрытия, а не PASS</p></details>
<table><thead><tr><th>Клетка</th><th>Семейство</th><th>Объект</th><th>Заезд</th><th>Наблюдений</th><th>Координаты и доказательство</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<script>const boxes=[...document.querySelectorAll('input[type=checkbox]')],search=document.querySelector('input[type=search]');function filter(){{const on=new Set(boxes.filter(x=>x.checked).map(x=>x.value)),q=search.value.toLowerCase();document.querySelectorAll('.obs').forEach(x=>x.classList.toggle('off',!on.has(x.dataset.f)||!x.dataset.q.toLowerCase().includes(q)));}}boxes.forEach(x=>x.onchange=filter);search.oninput=filter;document.querySelectorAll('circle').forEach(x=>x.onclick=()=>{{location.hash=x.dataset.id;document.getElementById(x.dataset.id).querySelector('details').open=true;}});filter();</script>''')
 print(run/'report.html',len(res['clusters']),'observations')
if __name__=='__main__':main()
