#!/usr/bin/env python3
"""Embed real smoke PNGs into the offline PSP preview; game files stay read-only."""
import argparse,base64,hashlib,json,subprocess
from datetime import datetime
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
a=argparse.ArgumentParser();a.add_argument('frames',type=Path);a.add_argument('--out',type=Path,default=ROOT/'build/psp-studio/PSP Студия.html');a.add_argument('--limit',type=int,default=24);args=a.parse_args()
frames=[];source={}
for p in sorted(args.frames.glob('*.png')):
 if p.name in ('contact.png',):continue
 with Image.open(p) as im:
  if im.size!=(480,272):continue
 b=p.read_bytes();source[p.name]=hashlib.sha256(b).hexdigest();frames.append(dict(name=p.stem,url='data:image/png;base64,'+base64.b64encode(b).decode()))
 if len(frames)>=args.limit:break
if not frames:raise SystemExit('Нет кадров PNG 480×272 в этой папке')
template=Path(__file__).with_name('studio.html').read_text();commit=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip()
identity=hashlib.sha256((template+json.dumps(source,sort_keys=True)).encode()).hexdigest()[:12]
meta=dict(product='PSP Студия',commit=commit,buildId=identity,buildTime=datetime.now().isoformat(timespec='seconds'),schemaVersion=1,testedChrome=None,knownLimitations=['превью PNG; монтаж PMF/AT3 и применение настроек в игру пока не включены'])
safe=lambda x:json.dumps(x,ensure_ascii=False).replace('<','\\u003c')
html=template.replace('__FRAMES_JSON__',safe(frames)).replace('__BUILD_JSON__',safe(meta));args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(html)
meta.update(standaloneSha256=hashlib.sha256(html.encode()).hexdigest(),sources=source,frames=len(frames));(args.out.parent/'BUILD.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');print(args.out)
