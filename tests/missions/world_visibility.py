#!/usr/bin/env python3
"""Exercise production room lookup and item drawing on original mission points.

City expectations exclude every original interior mesh bound. Interior cases
use centers of real walkable SHI1 triangles. The old height rule must fail.
This checks host world membership/draw submission, not PSP rendering speed.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/missions'))
from compile import Compiler
from census import in_room


def function(source, declaration):
    start = source.index(declaration + ' {')
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    main_src = read_main(ROOT / 'viewer/main.c')
    view = (ROOT / 'viewer/msn_view.c').read_text()
    floor = function(main_src, 'static int roomFloorAt(int i, float x, float y, float z)')
    lookup = function(main_src, 'static const char *npcRoomAt(float x, float y, float z)')
    visible = function(view, 'static int pointVisible(float x, float y, float z, const char *explicitRoom)')
    draw = function(view, 'static void drawItems(float ex, float ey, float ez, float t)')
    prefix = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "game_msn.h"
static struct {struct {char name[32]; ColWorld col;} room[8]; int nroom;} rooms;
static GameMsn M;
static float clock_; static int itemsDrawnLast=-1, draws;
static MsnLoc loc;
static const char *msn_arg_s_stub(const MsnFile *f,const MsnCmd *c,int i){(void)f;(void)c;(void)i;return "native_item";}
static const MsnLoc *msn_arg_loc_stub(const MsnFile *f,const MsnCmd *c,int i){(void)f;(void)c;(void)i;return &loc;}
#define msn_arg_s msn_arg_s_stub
#define msn_arg_loc msn_arg_loc_stub
#define MV_ITEMS_OLD 0
#define MV_ITEM_FAR 120.f
static void logf_(const char *fmt,...){(void)fmt;}
static void msnartDraw(const char *name,const float *p,float x,float y,float z,float t){(void)name;(void)p;(void)x;(void)y;(void)z;(void)t;draws++;}
static int checks,fails;
static void check(int ok,const char *label,const char *name){checks++;if(!ok){fails++;printf("FAIL %s %s\n",label,name);}}
'''
    suffix = r'''
int main(int argc,char **argv){
  if(argc!=3)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(!b||fread(b,1,n,f)!=(size_t)n||memcmp(b,"SHI1",4))return 2;fclose(f);
  unsigned nr;memcpy(&nr,b+4,4);if(nr>8)return 2;rooms.nroom=nr;
  for(unsigned i=0;i<nr;i++){
    unsigned off,end;memcpy(rooms.room[i].name,b+16+128*i,32);memcpy(&off,b+16+128*i+60,4);
    if(i+1<nr)memcpy(&end,b+16+128*(i+1)+60,4);else end=n;
    if(off>=end||end>(unsigned)n||colInit(&rooms.room[i].col,b+off,end-off))return 2;
  }
  f=fopen(argv[2],"r");if(!f)return 2;char name[160],want[32];float x,y,z;
  M.rt.nitems=1;M.rt.status=MSN_RUNNING;
  while(fscanf(f,"%159s %f %f %f %31s",name,&x,&y,&z,want)==5){
    const char *expected=strcmp(want,"-")?want:NULL,*actual=npcRoomAt(x,y,z);
    check(expected?actual&&!strcmp(actual,expected):!actual,"room",name);
    loc.pos[0]=x;loc.pos[1]=y;loc.pos[2]=z;
    for(int s=-1;s<rooms.nroom;s++){
      M.interior=s<0?NULL:rooms.room[s].name;
      int yes=expected?M.interior&&!strcmp(M.interior,expected):!M.interior;
      check(pointVisible(x,y,z,NULL)==yes,"point",name);
      M.rt.done[0]=0;M.rt.released[0]=0;M.rt.obj=MSN_OBJ_DELIVERY;draws=0;
      drawItems(x,y+1,z,0);check(draws==yes,"delivery",name);
      M.rt.done[0]=1;draws=0;drawItems(x,y+1,z,0);check(!draws,"collected",name);M.rt.done[0]=0;
      M.rt.obj=MSN_OBJ_DUMP;draws=0;drawItems(x,y+1,z,0);check(!draws,"unreleased",name);
      M.rt.released[0]=1;M.rt.relpos[0]=(MsnVec3){x,y,z};draws=0;
      drawItems(x,y+1,z,0);check(draws==yes,"released",name);
      draws=0;drawItems(x+121,y+1,z,0);check(!draws,"far",name);
    }
    // An explicit script room must override geometry and match its name.
    if(nr){M.interior=rooms.room[0].name;check(pointVisible(x,y,z,rooms.room[0].name),"explicit",name);
      M.interior=NULL;check(!pointVisible(x,y,z,rooms.room[0].name),"explicit-outside",name);}
  }
  fclose(f);for(unsigned i=0;i<nr;i++)colFree(&rooms.room[i].col);free(b);
  printf("RESULT checks=%d failures=%d\n",checks,fails);return fails?1:0;
}
'''
    result = {}
    for variant, predicate in [('green', visible), ('old-height',
            'static int pointVisible(float x,float y,float z,const char *r){(void)x;(void)z;(void)r;return (y < -10.f)==(M.interior!=NULL);}')]:
        c = args.out / f'{variant}.c'
        c.write_text(prefix + floor + lookup + predicate + draw + suffix)
        exe = args.out / variant
        subprocess.run(['cc', '-std=c99', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'), str(c),
                        str(ROOT / 'viewer/col.c'), str(ROOT / 'viewer/mission/msn_file.c'),
                        str(ROOT / 'viewer/mission/msn_ops.c'),
                        '-lm', '-o', str(exe)], check=True)
        for level in range(1, 8):
            packed = ROOT / ('build/interiors-l1.bin' if level == 1 else f'build/levels/l{level}/interiors-l{level}.bin')
            cases = args.out / f'l{level}.txt'
            if variant == 'green':
                compiler = Compiler(level)
                compiler.compile()
                points = []
                for i, loc_ in enumerate(compiler.pack.locs):
                    p = loc_['pos']
                    if not in_room(level, p):
                        points.append((f'city{i}', p, '-'))
                b = packed.read_bytes()
                nr, = struct.unpack_from('<I', b, 4)
                for room in range(nr):
                    at = 16 + room * 128
                    name = b[at:at+32].split(b'\0')[0].decode()
                    off, = struct.unpack_from('<I', b, at + 60)
                    ntri, = struct.unpack_from('<I', b, off + 24)
                    for i in range(ntri):
                        t = struct.unpack_from('<12f', b, off + 48 + i * 48)
                        if t[10] <= .5: continue
                        p = tuple(sum(t[j+k] for j in (0, 3, 6)) / 3 for k in range(3))
                        points.append((f'{name}-floor{i}', p, name))
                cases.write_text(''.join(f'{name} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f} {room}\n' for name,p,room in points))
            run = subprocess.run([str(exe.resolve()), str(packed), str(cases.resolve())], capture_output=True, text=True)
            (args.out / f'l{level}-{variant}.log').write_text(run.stdout + run.stderr)
            result[f'{level}-{variant}'] = {'rc':run.returncode, 'summary':run.stdout.splitlines()[-1],
                'col_sha256':hashlib.sha256(packed.read_bytes()).hexdigest(),
                'cases_sha256':hashlib.sha256(cases.read_bytes()).hexdigest()}
            print(level, variant, result[f'{level}-{variant}']['summary'], flush=True)
    result['source_sha256'] = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                              for p in ['viewer/main.c','viewer/msn_view.c','viewer/col.c']}
    (args.out / 'report.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if all(result[f'{l}-green']['rc']==0 for l in range(1,8)) and any(result[f'{l}-old-height']['rc']==1 for l in range(1,8)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
