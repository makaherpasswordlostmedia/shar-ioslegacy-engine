#!/usr/bin/env python3
"""Director 18:52: Kwik entry/menu <=26ms p95, complete real intervals, exact image pairs."""
import argparse,json,math,re,sys
from pathlib import Path
from PIL import Image,ImageChops

def check(kwik,menu,options,kwik_before,menu_before):
 errors=[];result={}
 def read(run):
  text=(run/'smoke.txt').read_text(errors='replace')
  if 'END' not in text.split():errors.append(str(run)+': incomplete run')
  return text
 k=read(kwik);m=read(menu);o=read(options)
 for scene in ['kwik_entry','kwik_inside']:
  rows=[s.split() for s in k.splitlines() if s.startswith('STAT '+scene+' ')]
  if len(rows)!=1:errors.append(scene+': missing STAT');continue
  row=dict(zip(rows[0][2::2],rows[0][3::2]));result[scene]=row
  if int(row['frames'])<100:errors.append(scene+': insufficient frames')
  if float(row['p95'])>26:errors.append(scene+': p95 >26ms')
  for key in ['missed','missvis','readerr','allocfail','geskip','memfail','gebad']:
   if int(row[key]):errors.append(scene+': '+key)
 if not re.search(r'HOMER .*room=KwikEMart',k):errors.append('Kwik interior not actually entered')
 for scene,log,kind in [('menu_idle',m,'main'),('menu_flight',m,'main'),('menu_options',o,'options')]:
  rows=[dict(re.findall(r'(\w+)=(\S+)',s)) for s in log.splitlines() if s.startswith('MENUPERF sc='+scene+' ')]
  vals=sorted(max(0,int(r['work_us'])-int(r['io_us']))/1000 for r in rows)
  if len(vals)<200:errors.append(scene+': missing menu measurement / too few frames');continue
  if any(r.get('kind')!=kind for r in rows):errors.append(scene+': wrong screen kind')
  p95=vals[math.ceil(.95*len(vals))-1];result[scene]=dict(frames=len(vals),p95_ms=p95,max_ms=max(vals),flying=sum(r['fly']=='1' for r in rows))
  if p95>26:errors.append(scene+': p95 >26ms')
  if scene=='menu_flight' and result[scene]['flying']<60:errors.append('no measured camera flight')
 result['pixel_pairs']={}
 for a,b,name in [(kwik,kwik_before,'kwik_inside'),(menu,menu_before,'menu_idle'),(menu,menu_before,'menu_options')]:
  x=Image.open(a/(name+'.png')).convert('RGB');y=Image.open(b/(name+'.png')).convert('RGB')
  if x.size!=(480,272) or x.size!=y.size:errors.append(name+': wrong framebuffer');continue
  count=sum(p!=(0,0,0) for p in ImageChops.difference(x,y).getdata());result['pixel_pairs'][name]=count
  if count:errors.append(name+': changed pixels')
 return errors,result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kwik',type=Path);p.add_argument('menu',type=Path);p.add_argument('options',type=Path);p.add_argument('--kwik-before',type=Path,required=True);p.add_argument('--menu-before',type=Path,required=True);a=p.parse_args()
 errors,result=check(a.kwik,a.menu,a.options,a.kwik_before,a.menu_before)
 result.update(status='FAIL' if errors else 'PASS',errors=errors,budget_p95_ms=26)
 (a.kwik/'perf9-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(bool(errors))
