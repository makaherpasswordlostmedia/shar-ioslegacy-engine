#!/usr/bin/env python3
"""Real SAP mutations prove Apu waiver cannot conceal another hero's missing GIC."""
import subprocess,struct,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'build/pcsay/entry-negative';out.mkdir(parents=True,exist_ok=True)
subprocess.run(['cc','-O2','-DAUDIO_HOST','-Iviewer','tests/sound/pcsay_host.c','viewer/sound.c','viewer/audio.c','-lm','-o','build/pcsay/pcsay'],cwd=ROOT,check=True)
for nm in ['sfx.sab','music.sap']:
 subprocess.run(['cp','-c',str(ROOT/'build/audio'/nm),str(out/nm)],check=True)
p=out/'music.sap';b=bytearray(p.read_bytes());assert b[:4]==b'SAP1';n,off=struct.unpack_from('<II',b,8);lost=0
for i in range(n):
 o=off+i*64;nm=bytes(b[o:o+28]).split(b'\0')[0]
 if nm.startswith(b'w_gic_hom_'):b[o:o+6]=b'x_gic_';lost+=1
assert lost==4;p.write_bytes(b)
checks=[('missing',out,'hom',[],['CHECK gicsrc FAIL','CHECK gic    FAIL']),('wrong-waiver',ROOT/'build/audio','hom',['--no-gic-source'],['CHECK gicsrc FAIL'])]
for nm,d,code,args,expected in checks:
 r=subprocess.run([str(ROOT/'build/pcsay/pcsay'),str(d)+'/',code,'-','-',*args],capture_output=True,text=True)
 (out/(nm+'.txt')).write_text(r.stdout+r.stderr);print(nm,r.returncode)
 assert r.returncode==1 and all(x in r.stdout for x in expected),r.stdout
print('PASS actual lost-Homer family and non-Apu waiver both rejected')
