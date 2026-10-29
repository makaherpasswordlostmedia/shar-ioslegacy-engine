#!/usr/bin/env python3
"""Read-only dependency0c0ca4e plus the ticket-only exporter fields in build/reference.
Never alters production alias source, the collect agent's artifact or release.
"""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/content-ticket-c3/reference';OUT.mkdir(parents=True,exist_ok=True)
base=subprocess.check_output(['git','show','0c0ca4e:tools/collect_export.py'],cwd=ROOT).decode()
s=base
patches=[("sparkle=0, persist=0, animCol=0, coins=0,", "sparkle=0, persist=0, animCol=0, coins=0, condition=0,"),
 ("elif c.op == 'GagPlayFMV': cur['fmv'] = str(a[0])", "elif c.op == 'GagPlayFMV': cur['fmv'] = str(a[0])\n        elif c.op == 'GagCheckCollCards': cur['condition'] = 1\n        elif c.op == 'GagCheckMovie': cur['condition'] = 2; cur['fmv'] = str(a[2])"),
 ("min(g['coins'], 255), 0, g['coinDelay']", "min(g['coins'], 255), (0 if os.environ.get('TICKET_CONTENT_C3_OLD') else g['condition']), g['coinDelay']")]
for old,new in patches:assert s.count(old)==1,old;s=s.replace(old,new)
s=s.replace('ROOT = Path(__file__).resolve().parents[1]',f'ROOT = Path({str(ROOT)!r})') # build-local path binding only
p=OUT/'collect_export.py';p.write_text(s)
canonical=ROOT.parent/'shar-psp-c3-collect-w/build/ship_stage/l3/collect-l3.shr'
subprocess.run(['cp','-c',str(canonical),str(OUT/'collect-base.shr')],check=True)
subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tools/collect_export.py'),'--level','3','--out',str(OUT/'without-alias.shr')],cwd=ROOT,check=True)
subprocess.run([str(ROOT/'.venv/bin/python'),str(p),'--level','3','--out',str(ROOT/'build/ship_stage/l3/collect-l3.shr')],cwd=ROOT,check=True)
f=ROOT/'build/ship_stage/l3/collect-l3.shr'
(OUT/'manifest.json').write_text(json.dumps(dict(dependency='0c0ca4e',source_sha256=hashlib.sha256(base.encode()).hexdigest(),composed_source_sha256=hashlib.sha256(s.encode()).hexdigest(),canonical_collect_source=str(canonical),canonical_collect_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest(),final_collect_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),patches='only ticket condition/fmv fields plus build-local ROOT path binding'),indent=2)+'\n')
