"""Execute production UIP1 and phone preload functions on real level packs, with ASan."""
import argparse,hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];O=R/'build/perf8-ui';O.mkdir(exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,default=R/'build/ship_stage');args=ap.parse_args();stage=args.stage.resolve()
u=(R/'viewer/ui.c').read_text();p=(R/'viewer/phone_view.c').read_text()
def function(source,name):
 start=source.index(name);brace=source.index('{',start);depth=1;i=brace+1
 while depth:
  depth+=(source[i]=='{')-(source[i]=='}');i+=1
 return source[start:i]+'\n'
types=u[u.index('typedef struct {\n  char magic'):u.index('\nenum { T_RECT')]
paks=u[u.index('typedef struct {\n  unsigned char *pak'):u.index('int uiScrReady')]
pre=r'''
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "ui.h"
typedef int SceUID;typedef unsigned SceSize;
#define PSP_O_RDONLY O_RDONLY
#define PSP_SEEK_END SEEK_END
#define PSP_SEEK_SET SEEK_SET
static unsigned opens,reads;
static int sceIoOpen(const char*p,int flags,int mode){opens++;return open(p,flags,mode);}
static int sceIoRead(int fd,void*p,unsigned n){reads++;return read(fd,p,n);}
static int sceIoClose(int fd){return close(fd);}
static long sceIoLseek(int fd,long off,int how){return lseek(fd,off,how);}
static void sceKernelDcacheWritebackRange(void*p,unsigned n){(void)p;(void)n;}
static void*memalign(unsigned a,size_t n){void*p=0;return posix_memalign(&p,a,n)?0:p;}
'''
globals=r'''
static unsigned char *pak;static const UiHdr *H;static const UiTex *tex;
static const UiItem *items;static const UiScreen *screens;static const UiFont *fonts;
static const unsigned *strOff;static const UiSGlyph *sfonts;static const UiIcon *icons;
static const UiSlot *slots;static const UiPt *pts;static const unsigned char **texPix;
static unsigned tagMask[UI_SCREEN_MAX],menuOff[UI_SCREEN_MAX];
static const char *scrRowTxt[UI_SCREEN_MAX][12];
#define PV_MAX 16
static char pvName[PV_MAX][16];static int pvLvl[PV_MAX],pvStars[PV_MAX][4];
#ifndef PHONE_LOAD_WARM_OLD
#define PHONE_LOAD_WARM_OLD 0
#endif
static int phoneWarmOld=PHONE_LOAD_WARM_OLD,warmCount;static char warmDir[256];
'''
body=function(u,'static int pakRead(')+paks
for name in ['void uiScrClose(','void uiScrWarmClear(','int uiScrWarm(','int uiScrWarmReady(','int uiScrOpen(','int uiScrReady(']:body+=function(u,name)
body+=function(p,'static int readList(')+function(p,'void phoneViewWarm(')
post=r'''
int main(int argc,char**argv){
 if(argc!=3)return 2;if(pakRead(argv[1]))return 2;UiPak main;pakGet(&main);
 unsigned hotIO=0,cases=0;
 for(int level=1;level<=7;level++){
  char dir[512],path[512];if(level==1)snprintf(dir,sizeof dir,"%s/",argv[2]);else snprintf(dir,sizeof dir,"%s/l%d/",argv[2],level);
  snprintf(path,sizeof path,"%sphone.shr",dir);
  uiScrWarmClear();if(uiScrOpen(path))return 3;unsigned size=scrPak.H->size;
  void*expected=malloc(size);memcpy(expected,scrPak.pak,size);UiPak original=scrPak;uiScrClose();
  phoneViewWarm(dir);unsigned before=opens;
  for(int i=0;i<32;i++){
   if(uiScrOpen(path))return 4;
   if(scrPak.H->size!=size||memcmp(expected,scrPak.pak,size))return 5;
   if(memcmp(scrPak.tagMask,original.tagMask,sizeof original.tagMask)||memcmp(scrPak.menuOff,original.menuOff,sizeof original.menuOff))return 6;
   if(pak!=main.pak||H!=main.H||texPix!=main.texPix)return 7;
   for(unsigned t=0;t<scrPak.H->ntex;t++)if(scrPak.texPix[t]!=scrPak.pak+scrPak.tex[t].offPix)return 8;
   scrPak.tagMask[0]^=32;scrPak.menuOff[0]=99;scrRowTxt[0][0]="temporary";
   if(scrPak.H->ntex)((const unsigned char**)scrPak.texPix)[0]=(const unsigned char*)expected;
   uiScrClose();if(scrRowTxt[0][0])return 9;cases++;
  }
  hotIO+=opens-before;
  if(uiScrOpen(path))return 10;int borrowed=scrPak.pak==warmPak.pak;uiScrWarmClear();
  if(borrowed?uiScrReady():!uiScrReady())return 11;uiScrClose();
  free(expected);
 }
 uiScrClose();uiScrWarmClear();free(main.pak);free((void*)main.texPix);
 printf("realLevelPacks7 opensDuring224Reopens%u cases%u totalOpens%u\n",hotIO,cases,opens);
 return hotIO?1:0;
}
'''
(O/'host.c').write_text(pre+types+globals+body+post)
results={}
for name,flags in [('new',[]),('old',['-DPHONE_LOAD_WARM_OLD=1'])]:
 exe=O/name;subprocess.run(['cc','-std=c11','-O1','-g','-fsanitize=address','-Iviewer',*flags,str(O/'host.c'),'-o',str(exe)],cwd=R,check=True)
 x=subprocess.run([exe,stage/'ui.shr',stage],capture_output=True,text=True);print(name,x.returncode,x.stdout,x.stderr);results[name]={'rc':x.returncode,'stdout':x.stdout,'stderr':x.stderr};assert x.returncode==(0 if name=='new' else 1)
results['inputs']={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [stage/'ui.shr',stage/'phone.shr',*[stage/f'l{n}/phone.shr' for n in range(2,8)]]}
(O/'proof.json').write_text(json.dumps(results,indent=2)+'\n')
