#!/usr/bin/env python3
"""Actual scheduling header against the measured V100 timer/prepare contract."""
from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/fe-ps2/clock-host';OUT.mkdir(parents=True,exist_ok=True)
facts=ROOT.parent/'shar-psp-ps2-w/knowledge/facts/ps2-main-menu-runtime.yaml'
data=json.loads(facts.read_text())
assert data['pending_table'][0]['elapsed_ms']==13040
assert data['table'][0]['next_delay_ms']==15000
assert data['flight_and_return'][0]['final_elapsed_ms']==12238
codes={}
for name,flags in [('new',[]),('clock-old',['-DFE_GAG_CLOCK_OLD=1']),('prepare-old',['-DFE_GAG_PREP_OLD=1'])]:
    binary=OUT/name
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-I'+str(ROOT/'viewer'),*flags,str(ROOT/'tests/menu/clock404_host.c'),'-o',str(binary)],check=True)
    r=subprocess.run([str(binary)],capture_output=True,text=True)
    (OUT/(name+'.log')).write_text(r.stdout+r.stderr);codes[name]=r.returncode
    print(name,'rc',r.returncode,r.stdout.strip().splitlines()[-1])
manifest={'facts_sha256':hashlib.sha256(facts.read_bytes()).hexdigest(),'header_sha256':hashlib.sha256((ROOT/'viewer/fe_gag_clock.h').read_bytes()).hexdigest(),'codes':codes}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
assert codes=={'new':0,'clock-old':1,'prepare-old':1},codes
print('PASS actual clock, retained timer, pending selection, real OLD controls')
