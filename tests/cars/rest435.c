#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "../../viewer/audio.c"
static unsigned audioStarts;static void note(int id,const char *why){(void)id;if(!strcmp(why,"skid"))audioStarts++;}
static int loadLevel(const char *path, ColWorld *w) {
  FILE *f = fopen(path, "rb"); if (!f) return -1;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15L);
  if (!data || fread(data, 1, size, f) != (size_t)size) { fclose(f); return -1; }
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  return colInit(w, data + co, ce - co) ? -2 : 0;   // данные уровня живут до конца процесса
}
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } floorData;
static ColWorld flat;
static void flatInit(void) {
  memset(&floorData, 0, sizeof floorData); memcpy(floorData.h.magic, "COL1", 4);
  floorData.h.ox = floorData.h.oz = -2000; floorData.h.cell = 4000; floorData.h.W = floorData.h.H = 1; floorData.h.ntri = floorData.h.nref = 2;
  floorData.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  floorData.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  floorData.start[1] = 2; floorData.refs[0] = 0; floorData.refs[1] = 1;
  colInit(&flat, &floorData, sizeof floorData);
}


int main(int argc,char **argv){ColWorld real={0};const ColWorld *w=&flat;flatInit();float px=0,pz=0;
if(argc>1 && strcmp(argv[1],"flat")){if(loadLevel(argv[1],&real)){fprintf(stderr,"bad level\n");return 2;}w=&real;px=argc>2?atof(argv[2]):283.333333;pz=argc>3?atof(argv[3]):283.333333;}
for(int k=0;k<2;k++){const char *name=k?"famil_v":"marge_v";CarParams p;carParamsFor(name,&p);Car c;float ground=0;colGround(w,px,pz,200,-200,&ground,0);carInit(&c,&p,w,px,ground+.5f,pz,argc>7?atof(argv[7]):0);CarInput in={0};int audioReady=argc>5 && !audioInit(k?argv[6]:argv[5]);if(audioReady){audioPlayerCar(name);if(strcmp(car->name,name)){fprintf(stderr,"Wrong audio profile %s\n",name);return 2;}audioNote=note;}audioStarts=0;FILE *pcmFile=0;if(argc>8){char fn[1024];snprintf(fn,sizeof fn,"%s-%s.s16le",argv[8],name);pcmFile=fopen(fn,"wb");if(!pcmFile)return 2;}
float mn[7],mx[7];for(int j=0;j<7;j++){mn[j]=1e9f;mx[j]=-1e9f;}int slip=0,starts=0,last=0,pcmPeak=0,mixDue=0;float maxv=0,maxvl=0;
for(int i=0;i<60*35;i++){carUpdate(&c,w,&in,1.f/60);if(audioReady){audioSkid(c.grounded&&c.slip?fminf(1.f,fabsf(c.vl)/6.f+.3f):0,0);short pcm[FRAMES*2];mixDue+=735;while(mixDue>=FRAMES){audioHostMix(pcm,FRAMES);mixDue-=FRAMES;if(i>=60*5){if(pcmFile)fwrite(pcm,sizeof(short),FRAMES*2,pcmFile);for(int j=0;j<FRAMES*2;j++)if(abs(pcm[j])>pcmPeak)pcmPeak=abs(pcm[j]);}}}if(i<60*5)continue;float v[]={c.x,c.y,c.z,c.gx,c.gz,c.ry,c.h};for(int j=0;j<7;j++){mn[j]=fminf(mn[j],v[j]);mx[j]=fmaxf(mx[j],v[j]);}int sk=c.grounded&&c.slip;slip+=sk;if(sk&&!last)starts++;last=sk;maxv=fmaxf(maxv,fabsf(c.v));maxvl=fmaxf(maxvl,fabsf(c.vl));if(argc>4 && strcmp(argv[4],"0"))printf("TRACE %s %d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %.9g %.9g %.9g %.9g\n",name,i,c.x,c.y,c.z,c.gx,c.gz,c.v,c.vl,c.slip,c.comp[0],c.comp[1],c.comp[2],c.comp[3]);}
printf("REST %s audioStarts=%u pcmPeak=%d dx=%.9g dy=%.9g dz=%.9g pitch=%.9g roll=%.9g yaw=%.9g ry=%.9g skidFrames=%d skidStarts=%d v=%.9g vl=%.9g r=%.9g lim=%.9g\n",name,audioStarts,pcmPeak,mx[0]-mn[0],mx[1]-mn[1],mx[2]-mn[2],mx[3]-mn[3],mx[4]-mn[4],mx[6]-mn[6],mx[5]-mn[5],slip,starts,maxv,maxvl,c.p.wheelRad,c.lim);if(pcmFile)fclose(pcmFile);if(audioReady)audioShutdown();
Car idle=c;in.throttle=1;for(int j=0;j<60;j++)carUpdate(&c,w,&in,1.f/60);
if(fabsf(c.v)<.5f){fprintf(stderr,"FAIL wake throttle %s\n",name);return 1;}
c=idle;in.throttle=0;c.vel[0]+=1.f;float oldX=c.x;carUpdate(&c,w,&in,1.f/60);
if(fabsf(c.x-oldX)<.001f){fprintf(stderr,"FAIL wake impulse %s\n",name);return 1;}
printf("WAKE %s throttle and impulse PASS\n",name);}

}
