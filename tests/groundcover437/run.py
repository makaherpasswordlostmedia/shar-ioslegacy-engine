#!/usr/bin/env python3
from pathlib import Path
import subprocess,argparse
r=Path(__file__).resolve().parents[2]
def function(file,name):
 s=(r/file).read_text();start=s.index(name);start=s.rfind('static ',0,start);brace=s.index('{',start);depth=1;i=brace+1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[start:i]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=r/'build/groundcover437');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
source=(r/'tests/groundcover437/host.c.in').read_text().replace('#include "groundcover.h"','#include "groundcover.h"\n#include "car.h"')
for key,name,file in [('SAMPLE','skyTexel(', 'viewer/main_camera.h'),('COLOUR','groundCoverColour(', 'viewer/main_camera.h'),('DRAW','groundCoverDraw(', 'viewer/main_camera.h'),('FOG','fogBase(', 'viewer/main_stream.h')]:source=source.replace("\n"+key+"\n","\n"+function(file,name)+"\n")
stub=(r/'tests/shadow433/stub/pspgu.h').read_text().replace('#define GU_DITHER 99','#define GU_DITHER 99\n#define GU_CULL_FACE 100\n#define GU_DEPTH_TEST 101\n#define GU_TRIANGLE_FAN 102\n#define GU_VIEW 103\n#define GU_TRANSFORM_2D 104');(a.out/'pspgu.h').write_text(stub)
code=a.out/'host.c';code.write_text(source)
for mode in ('new','old'):
 exe=a.out/mode;flags=[] if mode=='new' else ['-DGROUND_COVER_OLD=1']
 subprocess.run(['cc','-O2','-std=c11','-I',str(a.out),'-I',str(r/'viewer'),*flags,str(code),str(r/'viewer/col.c'),'-lm','-o',str(exe)],check=True)
 result=subprocess.run([str(exe)],capture_output=True,text=True);(a.out/f'{mode}.log').write_text(result.stdout+result.stderr)
 print(result.stdout.splitlines()[-1]);assert result.returncode==(0 if mode=='new' else 1),result.stdout
print('PASS actual runtime ground-cover / GROUND_COVER_OLD red')
