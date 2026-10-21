// Disc mailbox at b2_mail placement; car/prop physics, one recorded 12m/s approach.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "props.h"
int main(int argc,char **argv) {
 if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);
 unsigned char *b=malloc(n);if(fread(b,1,n,f)!=n)return 2;fclose(f);
 unsigned po=*(unsigned*)(b+96),co=*(unsigned*)(b+92);Props p;ColWorld w;
 if(colInit(&w,b+co,n-co)||propsInit(&p,b+po,*(unsigned*)(b+po+40)))return 2;
 unsigned idx=0;float near=1e9f;
 for(unsigned i=0;i<p.ninst;i++){float d=hypotf(p.def[i].x-219.526f,p.def[i].z-168.508f);if(d<near){near=d;idx=i;}}
 printf("MATERIAL mass=%.3f half=%.3f,%.3f,%.3f centre=%.3f,%.3f,%.3f\n",p.types[p.def[idx].type].mass,p.st[idx].hx,p.st[idx].hy,p.st[idx].hz,p.st[idx].x,p.st[idx].y,p.st[idx].z);
 int particle,bi;propsTypeFx(&p,p.def[idx].type,&particle,&bi);
 printf("SOURCE mailbox idx=%u placement_error=%.6f particle=%d break=%d\n",idx,near,particle,bi);
 if(near>.001f||particle!=6)return 2;
 for(unsigned i=0;i<p.ninst;i++)p.st[i].hidden=i!=idx;
 float y;if(!colGround(&w,221.3f,174.24f,10,-10,&y,0))return 2;
 Car c;carInit(&c,0,&w,221.3f,y,174.24f,3.14159265f+17.2f*.0174533f);
 c.vel[0]=-3.54f;c.vel[2]=-11.46f;
#ifdef MAIL_REF_OLD
 c.vel[0]=c.vel[2]=0; // negative: missing impulse; identical evidence criterion
#endif
 float x0=p.st[idx].x,z0=p.st[idx].z,max=0;
 for(int fr=0;fr<560;fr++) {
  CarInput in={0};carUpdate(&c,&w,&in,1.f/50);propsUpdate(&p,&w,&c,1.f/50);
#ifdef MAIL_REF_TRACE
  if(fr<100 || fr%20==0)printf("TRACE %d car=%.3f,%.3f speed=%.3f,%.3f mail=%.3f,%.3f,%.3f vel=%.3f,%.3f,%.3f\n",fr,c.x,c.z,c.vel[0],c.vel[2],p.st[idx].x,p.st[idx].y,p.st[idx].z,p.st[idx].vel[0],p.st[idx].vel[1],p.st[idx].vel[2]);
#endif
  float d=hypotf(p.st[idx].x-x0,p.st[idx].z-z0);if(d>max)max=d;
 }
 printf("DISTANCE %.9g awake=%d hidden=%d\n",max,!p.st[idx].asleep,p.st[idx].hidden);
 propsFree(&p);colFree(&w);free(b);return 0;
}
