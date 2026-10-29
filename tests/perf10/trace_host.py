#!/usr/bin/env python3
"""Compile production trace functions: OLD repeats open per phase; NEW writes immediately."""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
from pathlib import Path
import re,subprocess
ROOT=Path(__file__).resolve().parents[2]
source=read_main(ROOT/'viewer/main.c')
a=source.index('#ifndef TRACE_OPEN_OLD\nstatic SceUID trFd');b=source.index('// Правки 259/252',a)
body=source[a:b]
harness=r'''
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef int SceUID;
enum {PSP_O_WRONLY=1,PSP_O_CREAT=2,PSP_O_APPEND=4,BBP_VBLANK=8,BBP_N=9};
static unsigned now,smkIoUs,bbBeat=42,geGuardHits;
static int opens,closes,writes,failWrite,trLeft=3;
const char *const bbPhName[]={"input","car","world","rooms","msn","traffic","stream","gesync","vblank"};
static char output[16384];static int outputN;
static unsigned sceKernelGetSystemTimeLow(void){return now;}
static void sibling(char *s,const char *n){strcpy(s,n);}
static int sceIoOpen(const char*p,int f,int m){(void)p;(void)f;(void)m;opens++;now+=10000;return 7;}
static int sceIoClose(int f){(void)f;closes++;now+=1000;return 0;}
static int msioWriteRaw(int f,const char*s,unsigned n){(void)f;writes++;now+=10;if(failWrite){failWrite=0;return -1;}memcpy(output+outputN,s,n);outputN+=n;output[outputN]=0;return n;}
@BODY@
int main(int argc,char**argv){
 for(int frame=0;frame<3;frame++)for(int phase=0;phase<9;phase++)trPhase(phase);
 if(writes!=27||trLeft!=0)return 2;
 FILE*f=fopen(argv[1],"w");if(!f)return 2;fwrite(output,1,outputN,f);fclose(f);
 printf("opens=%d writes=%d closes=%d synchronous_us=%u\n",opens,writes,closes,now);
 if(opens!=1)return 1;
 // A failed write closes the stale handle; the very next line reopens and persists.
 failWrite=1;trLine("failed\n",7);trLine("recovered\n",10);
 if(opens!=2||closes!=1||strcmp(output+outputN-10,"recovered\n"))return 2;
 return 0;
}
'''
out=ROOT/'build/perf10-trace';out.mkdir(parents=True,exist_ok=True)
logs=[]
for label,flags,rc in [('new',[],0),('old',['-DTRACE_OPEN_OLD=1'],1)]:
 c=out/(label+'.c');c.write_text(harness.replace('@BODY@',body))
 exe=out/label;subprocess.run(['cc','-O2','-std=c11',*flags,str(c),'-o',str(exe)],check=True)
 run=subprocess.run([str(exe),str(out/(label+'.trace'))],capture_output=True,text=True)
 (out/(label+'.log')).write_text(run.stdout+run.stderr);print(label,run.returncode,run.stdout.strip())
 assert run.returncode==rc
 logs.append(re.sub(r'us=\d+','us=TIME',(out/(label+'.trace')).read_text()))
assert logs[0]==logs[1]
print('PASS immediate trace payload preserved; OLD repeat-open RED; write-error recovery GREEN')
