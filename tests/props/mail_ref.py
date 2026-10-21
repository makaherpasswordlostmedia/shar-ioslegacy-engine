#!/usr/bin/env python3
"""Offline b2_mail distance vs the coupled port approach, without tuning props.

Source-native placement and 12m/s velocity from b2_mail recipe; target is maximum
horizontal displacement of the recorded mailbox, not distance travelled by car.
A mismatch is a report for the physics owner; this script never fixes the game.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--evidence',type=Path,default=ROOT.parent/'shar-psp')
ap.add_argument('--level',default='build/level.shr')
a=ap.parse_args();out=ROOT/'build/mail-ref-gate';out.mkdir(exist_ok=True)
source=a.evidence/'build/ps2ref/answers/b2_mail/trace.tsv'
r=list(csv.DictReader(source.open(),delimiter='\t'));start=r[0]
native=max(math.hypot(float(x['mb_x'])-float(start['mb_x']),float(x['mb_z'])-float(start['mb_z'])) for x in r)
# Printed positions have 3 decimals: two 2D endpoints, each +/-0.0005m.
rounding=2*math.sqrt(2)*.0005
band=[native-rounding,native+rounding];res={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'native':native,'precision_band':band}
fail=False
for tag,flags in [('green',[]),('red',['-DMAIL_REF_OLD=1'])]:
    binary=out/tag
    subprocess.run(['cc','-O2','-DSKIN_HOST','-I','viewer',*flags,'tests/props/mail_ref.c','viewer/props.c','viewer/car.c','viewer/col.c','-lm','-o',str(binary)],cwd=ROOT,check=True)
    text=subprocess.check_output([str(binary),a.level],cwd=ROOT,text=True)
    (out/f'{tag}.txt').write_text(text)
    dist=float(re.search(r'DISTANCE (\S+)',text)[1]);ok=band[0]<=dist<=band[1]
    res[tag]={'distance':dist,'pass':ok}
    print(('PASS' if ok else 'FAIL')+f' mailbox {tag}: {dist:.3f}m; native {native:.3f}m (precision {rounding:.4f}m)')
    fail|=ok if tag=='red' else not ok
(out/'result.json').write_text(json.dumps(res,indent=2)+'\n')
print('RESULT', 'FAIL (forward mismatch to physics owner)' if fail else 'PASS')
raise SystemExit(fail)
