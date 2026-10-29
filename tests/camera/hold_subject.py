#!/usr/bin/env python3
"""Camera collision recovery must carry its eye with the same subject only."""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import json
import subprocess
from pathlib import Path
from chase_motion import ROOT, function


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--old',action='store_true')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    helper=function(read_main(ROOT/'viewer/main.c'),'csHeldEye')
    old_define=1 if args.old else 0
    source=f'#define CAMERA_SUBJECT_HANDOFF_OLD {old_define}\n#include <stdio.h>\n'+helper+r'''
int main(void){float p[3],e[3],r[3],out[3];int same;
 while(scanf("%f%f%f%f%f%f%f%f%f%d",p,p+1,p+2,e,e+1,e+2,r,r+1,r+2,&same)==10){
  csHeldEye(p,e,r,same,out);printf("%.8g %.8g %.8g\n",out[0],out[1],out[2]);
 }return 0;}
'''
    (args.out/'hold.c').write_text(source)
    subprocess.run(['cc','-std=c11','-O2',str(args.out/'hold.c'),'-o',str(args.out/'hold')],check=True)
    cases=[]
    # Real rendered camera immediately before automatic exit on F10-5.
    eye=[-163.437,5.574,243.451];old_pivot=[-164.301,2.639,235.326]
    relative=[eye[k]-old_pivot[k] for k in range(3)]
    new_pivot=[-165.916,2.348,236.049]
    cases.append(('recorded car to Homer handoff',[*new_pivot,*eye,*relative,0],eye))
    cases.append(('recorded handoff back',[*old_pivot,*eye,*[eye[k]-new_pivot[k] for k in range(3)],0],eye))
    for hz in (30,60,120):
        for axis in range(3):
            for speed in (0,5,40):
                delta=speed/hz;p=old_pivot.copy();p[axis]+=delta
                expected=eye.copy();expected[axis]+=delta
                cases.append(('same subject tracks translation',[*p,*eye,*relative,1],expected))
                for shift in (-10,-1.5,.2,8):
                    p=old_pivot.copy();p[axis]+=shift
                    cases.append(('different subject retains world eye',[*p,*eye,*relative,0],eye))
    result=subprocess.run([str(args.out/'hold')],input='\n'.join(' '.join(map(str,row)) for _,row,_ in cases)+'\n',capture_output=True,text=True,check=True)
    values=[[float(v) for v in line.split()] for line in result.stdout.splitlines()]
    assert len(values)==len(cases),'missing camera handoff samples'
    failures=[dict(case=name,actual=value,expected=expected) for (name,_,expected),value in zip(cases,values) if max(abs(a-b) for a,b in zip(value,expected))>.00004]
    (args.out/'report.json').write_text(json.dumps(dict(checks=len(cases),failures=failures,old=args.old),indent=2)+'\n')
    print(f"{'FAIL' if failures else 'PASS'} camera held eye checks={len(cases)} failures={len(failures)} old={args.old}")
    return int(bool(failures))


if __name__=='__main__':raise SystemExit(main())
