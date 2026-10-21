#!/usr/bin/env python3
"""278: inspect partition, or --apply LAST after all gameplay merges; one unchanged translation unit."""
import argparse,ast,datetime,hashlib,json,re,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from main_source import read_main
PARTS=[('main_state.h',None),('main_stream.h','// ---------- стриминг клеток'),('main_camera.h','// ---- камера за машиной'),('main_render.h','// ---------- карта высот'),('main_probe.h','// ---------- тест-прогон v2'),('main_rooms.h','// ---------- 11.2: комнаты'),('main_collect.h','// ---------- В5: карточки'),('main_frontend.h','// ---------- 12а: заставка'),('main_save.h','// ---- настройки игрока из меню'),('main_levels.h','// ---------- уровни 1–7'),('main_loop.h','int main(int argc,')]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
p=ROOT/'viewer/main.c';raw=p.read_text();source=read_main(p)
assert 'MAIN_MODULES_OLD' not in raw,'already split; merge gameplay before this last step'
starts=[0 if marker is None else source.index(marker) for _,marker in PARTS];assert starts==sorted(starts) and len(set(starts))==len(starts)
blocks=[]
for i,(name,marker) in enumerate(PARTS):
 begin=starts[i];end=starts[i+1] if i+1<len(starts) else len(source);text=source[begin:end];depth=0
 for line in text.splitlines():
  if re.match(r'^\s*#\s*(if|ifdef|ifndef)\b',line):depth+=1
  elif re.match(r'^\s*#\s*endif\b',line):depth-=1
  assert depth>=0,(name,line)
 assert depth==0,(name,'preprocessor conditional crosses module')
 blocks.append((name,text))
plan=dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),source_bytes=len(source.encode()),modules=[dict(name=n,lines=s.count('\n'),bytes=len(s.encode())) for n,s in blocks],applied=a.apply)
if not a.apply:print(json.dumps(plan,indent=2));raise SystemExit()
archive=ROOT/'_backups/main278'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');archive.mkdir(parents=True)
shutil.copy2(p,archive/'main.c');(archive/'manifest.json').write_text(json.dumps(plan,indent=2)+'\n')
out=ROOT/'build/main278';out.mkdir(parents=True,exist_ok=True);(out/'legacy.c').write_text(source)
for name,text in blocks:
 target=ROOT/'viewer'/name
 if target.exists():shutil.copy2(target,archive/name)
 target.write_text(text)
p.write_text('// SHAR main assembly: included modules share the original static state and order.\n// One translation unit; no gameplay/ABI/optimizer boundary changes.\n#ifndef MAIN_MODULES_OLD\n#define MAIN_MODULES_OLD 0\n#endif\n#if MAIN_MODULES_OLD\n#include "../build/main278/legacy.c" // prepared by tests/main_split/check.py\n#else\n'+''.join('#include "'+n+'"\n' for n,_ in blocks)+'#endif\n')
assert read_main(p)==source,'assembly differs'
# Update literal main readers added by later gameplay branches as part of this last step.
# Existing consumers already use read_main, so no repeated imports or assertion changes.
for folder in ['tools','tests']:
 for q in (ROOT/folder).rglob('*.py'):
  if q.name in ['split_main.py','main_source.py'] or q==ROOT/'tests/main_split/check.py':continue
  text=q.read_text(errors='replace')
  if 'main.c' not in text:continue
  try:tree=ast.parse(text)
  except SyntaxError:continue
  lines=text.encode().splitlines(keepends=True);starts=[];pos=0
  for line in lines:starts.append(pos);pos+=len(line)
  edits=[]
  for x in ast.walk(tree):
   if not (isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr in ['read_text','read_bytes'] and 'main.c' in ast.unparse(x.func.value)):continue
   val=ast.get_source_segment(text,x.func.value);kw=', errors="replace"' if x.keywords else ''
   value='read_main('+val+kw+')'+('.encode()' if x.func.attr=='read_bytes' else '')
   edits.append((starts[x.lineno-1]+x.col_offset,starts[x.end_lineno-1]+x.end_col_offset,value.encode()))
  if not edits:continue
  blob=text.encode()
  for begin,end,value in sorted(edits,reverse=True):blob=blob[:begin]+value+blob[end:]
  text=blob.decode()
  if 'from main_source import read_main' not in text:
   tree=ast.parse(text);insert=0
   for node in tree.body:
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) and insert==0:insert=node.end_lineno
    elif isinstance(node,ast.ImportFrom) and node.module=='__future__':insert=node.end_lineno
    else:break
   depth=len(q.relative_to(ROOT).parts)-1
   boot=f'from pathlib import Path as _MainPath\nimport sys as _MainSys\n_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[{depth}]/"tools"))\nfrom main_source import read_main\n'
   lines=text.splitlines(keepends=True);lines.insert(insert,boot);text=''.join(lines)
  q.write_text(text)
  print('updated source consumer',q.relative_to(ROOT))

print(json.dumps(plan,indent=2));print('backup',archive)
