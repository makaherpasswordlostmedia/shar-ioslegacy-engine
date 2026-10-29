/* Every authored foliage volume, isolated only to separate its response from
   unrelated walls/trees next to it. World-space sweeps are all445.c, separately. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static int trial(ColWorld*w,float h,float speed,float e,int rest){
 Car c;float dx=sinf(h),dz=cosf(h),off=rest?0:e+5;
 carInit(&c,0,w,-dx*off,0,-dz*off,h);carSetSpeed(&c,speed);CarInput in={1,0,0,0};
 float ax=c.x,az=c.z,still=0;
 for(int i=0;i<600;i++){
  carUpdate(&c,w,&in,1.f/60);
  if(!isfinite(c.x)||!isfinite(c.y)||!isfinite(c.z))return 1;
  if(c.x*dx+c.z*dz>e+c.p.halfL+.25f)return 0;
  if(hypotf(c.x-ax,c.z-az)>.5f){ax=c.x;az=c.z;still=0;}else still+=1.f/60;
  if(still>3.f)return 1;
 }return 1;
}
int main(int argc,char**argv){
 if(argc<2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char*data=malloc(n);if(fread(data,1,n,f)!=(size_t)n)return 2;fclose(f);unsigned co=*(unsigned*)(data+92);ColWorld original;if(colInit(&original,data+co,n-co))return 2;
 int objects=0,runs=0,bad=0;
 for(int t=COL_BOX;t<=COL_CYL;t++)for(unsigned id=0;id<(t==COL_BOX?original.nbox:original.ncyl);id++){
  if((t==COL_BOX?original.box[id].pad:original.cyl[id].pad[0])!=1.f)continue;
  unsigned char blob[512]={0};ColHdr *hd=(void*)blob;memcpy(hd->magic,"COL1",4);hd->ox=hd->oz=-100;hd->cell=200;hd->W=hd->H=1;hd->ntri=2;hd->nbox=t==COL_BOX;hd->ncyl=t==COL_CYL;hd->nref=3;
  ColTri*tr=(void*)(hd+1);tr[0]=(ColTri){{-100,0,-100},{100,0,100},{100,0,-100},{0,1,0}};tr[1]=(ColTri){{-100,0,-100},{-100,0,100},{100,0,100},{0,1,0}};
  ColBox *bx=(void*)(tr+2);ColCyl*cy=(void*)(tr+2);unsigned *st;
  if(t==COL_BOX){*bx=original.box[id];bx->c[0]=bx->c[2]=0;bx->c[1]=1;st=(void*)(bx+1);}else{*cy=original.cyl[id];cy->c[0]=cy->c[2]=0;cy->c[1]=1;st=(void*)(cy+1);}
  st[0]=0;st[1]=3;st[2]=0;st[3]=1;st[4]=t<<29;
  ColWorld w;if(colInit(&w,blob,(unsigned)((unsigned char*)(st+5)-blob)))return 2;objects++;
  for(int di=0;di<4;di++)for(int si=0;si<4;si++){
   float h=di*1.5707963268f,dx=sinf(h),dz=cosf(h),e;
   if(t==COL_CYL)e=cy->r+cy->halfLen*fabsf(cy->axis[0]*dx+cy->axis[2]*dz);
   else e=bx->h[0]*fabsf(bx->ax[0]*dx+bx->ax[2]*dz)+bx->h[1]*fabsf(bx->ay[0]*dx+bx->ay[2]*dz)+bx->h[2]*fabsf(bx->az[0]*dx+bx->az[2]*dz);
   int fail=trial(&w,h,si*20.f/3.6f,e,si==0);bad+=fail;runs++;if(fail)printf("FAIL type=%d id=%u dir=%d speed=%d\n",t,id,di,si*20);
  }colFree(&w);
 }
 printf("%s objects=%d trials=%d stuck=%d\n",bad?"FAIL":"PASS",objects,runs,bad);colFree(&original);free(data);return !!bad;
}
