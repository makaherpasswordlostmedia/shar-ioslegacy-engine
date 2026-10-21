/* Diagnostic baseline, not PS2 acceptance: ps2-car-gravity is only a car trace.
 * Reads a real level's COL1/PRP2 and advances its first prop in free fall.
 * This exact measurement can be compared to future question B115. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "props.h"
static uint32_t u32(const unsigned char *p){uint32_t v;memcpy(&v,p,4);return v;}
int main(int argc,char **argv){
 if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
 fseek(f,0,SEEK_END);long sz=ftell(f);rewind(f);if(sz<104)return 2;
 unsigned char *b=malloc((size_t)sz);if(!b||fread(b,1,(size_t)sz,f)!=(size_t)sz)return 2;fclose(f);
 if(memcmp(b,"SHR7",4))return 2;
 uint32_t co=u32(b+92),po=u32(b+96),pv=u32(b+88),ce=(uint32_t)sz;
 if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
 if(!co||co>=ce||!po||po+64>(uint32_t)sz)return 2;
 ColWorld col;Props props;uint32_t ps=u32(b+po+40);
 if((uint64_t)po+ps>(uint32_t)sz||colInit(&col,b+co,ce-co)||propsInit(&props,b+po,ps)||!props.ninst)return 2;
 PropState *s=&props.st[0];s->x=220.f;s->z=172.f;s->y=100.f;s->asleep=s->hidden=s->fresh=0;
 s->q[0]=1.f;s->q[1]=s->q[2]=s->q[3]=0.f;memset(s->vel,0,sizeof s->vel);memset(s->w,0,sizeof s->w);
 props.ninst=1;double st=0,sv=0,stt=0,stv=0;int n=60;float dt=1.f/60.f;
 for(int k=0;k<n;k++){propsAdvance(&props,&col,dt);double t=(k+1)*dt,v=s->vel[1];st+=t;sv+=v;stt+=t*t;stv+=t*v;}
 double g=-(n*stv-st*sv)/(n*stt-st*st);
 printf("prop_type=%u frames=%d gravity_m_s2=%.6f y=%.6f vy=%.6f source=%s PS2=unmeasured\n",props.def[0].type,n,g,s->y,s->vel[1],argv[1]);
 int rc=!((g>0&&g<100)&&s->y>80.f);propsFree(&props);free(b);return rc;
}
