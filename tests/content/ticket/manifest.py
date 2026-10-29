#!/usr/bin/env python3
"""Hash this task's exact stage, original voices and read-only composed dependency."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from ticket_audio import voices
OUT=ROOT/'build/content-ticket-c3'
paths=['build/ship_stage/EBOOT.PBP','build/ship_stage/l3/collect-l3.shr','build/ship_stage/l3/ticket.shr',
       'build/ship_stage/l3/audio/music.sap','build/ship_stage/l3/audio/sfx.sab','build/ship_stage/movies/fmv8.smv',
       'build/ship_stage/l3/player.shr','build/ship_stage/l3/interiors-l3.bin','build/ship_stage/l3/interiors-l3-gfx.bin',
       'build/content-ticket-c3/reference/collect_export.py','build/content-ticket-c3/reference/collect-base.shr',
       'build/content-ticket-c3/reference/without-alias.shr']
paths += [f"hit-and-run-web/source/game/{v['file']}" for v in voices()]
def row(name):
 p=ROOT/name;return dict(path=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
data=dict(code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          dependency='0c0ca4e',artifacts=[row(p) for p in paths],
          reference=json.loads((OUT/'reference/manifest.json').read_text()))
(OUT/'artifacts.json').write_text(json.dumps(data,indent=2)+'\n')
for r in data['artifacts']:assert row(r['path'])==r
print('artifacts',len(paths),'SHA256 PASS')
