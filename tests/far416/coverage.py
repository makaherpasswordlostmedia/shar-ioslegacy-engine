#!/usr/bin/env python3
"""Полный сохранённый прогон и две настоящие порчи покрытия; сеть и эмулятор не нужны"""
import sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
base=Path(sys.argv[1]).resolve()
out=root/'build/codex4-far416/coverage';out.mkdir(parents=True,exist_ok=True)
files=sorted(base.glob('L*h*_*.png'))
if not files:raise SystemExit('FAIL no captured frames')
py=sys.executable;measure=root/'tests/far416/measure.py'
def run(tag,path,expect):
 r=subprocess.run([py,str(measure),str(path)],capture_output=True,text=True)
 (out/(tag+'.log')).write_text(r.stdout+r.stderr)
 print(tag,'PASS' if r.returncode==expect else 'FAIL',r.returncode)
 return r.returncode==expect
ok=run('green',base,0)
missing=next(p for p in files if p.name.endswith('_n.png'))
for tag,skip in [('red-level',lambda p:p.name.startswith('L7')),('red-repeat',lambda p:p==missing)]:
 d=out/tag;d.mkdir(exist_ok=True)
 for p in files:
  q=d/p.name
  if not skip(p) and not q.exists():q.symlink_to(p)
 ok=run(tag,d,2) and ok
raise SystemExit(not ok)
