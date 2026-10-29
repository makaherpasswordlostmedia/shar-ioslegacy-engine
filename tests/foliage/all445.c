/* #445: enumerate actual ATC foliage in COL1, approach at 20/40/60 km/h
   and start with throttle inside each volume. No world geometry is removed.
   Report obstruction candidates independently from family acceptance. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld w;
static float extent(int type,unsigned i,float dx,float dz){
 if(type==COL_CYL){const ColCyl*c=w.cyl+i;return c->r+c->halfLen*fabsf(c->axis[0]*dx+c->axis[2]*dz);}
 const ColBox*b=w.box+i;return b->h[0]*fabsf(b->ax[0]*dx+b->ax[2]*dz)+b->h[1]*fabsf(b->ay[0]*dx+b->ay[2]*dz)+b->h[2]*fabsf(b->az[0]*dx+b->az[2]*dz);
}
int main(int argc,char**argv){
 if(argc<2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char*b=malloc(n);if(fread(b,1,n,f)!=(size_t)n)return 2;fclose(f);
 unsigned co=*(unsigned*)(b+92);if(colInit(&w,b+co,n-co))return 2;
 int total=0,passed=0,stuck=0,noGround=0,objects=0;
 puts("type,id,x,z,direction,speed,start_rest,result,progress,still_seconds,wall_type,wall_id,wall_material");
 for(int typ=COL_BOX;typ<=COL_CYL;typ++)for(unsigned i=0;i<(typ==COL_BOX?w.nbox:w.ncyl);i++){
  const float*p=typ==COL_BOX?w.box[i].c:w.cyl[i].c;
  if((typ==COL_BOX?w.box[i].pad:w.cyl[i].pad[0])!=1.f)continue;objects++;
  for(int di=0;di<4;di++)for(int si=0;si<4;si++){
   float h=di*1.5707963268f,dx=sinf(h),dz=cosf(h),e=extent(typ,i,dx,dz),off=si?e+5.f:0.f;
   float x=p[0]-dx*off,z=p[2]-dz*off,g;colSetFoliagePass(1);
   if(!colGround(&w,x,z,p[1]+3.f,-1000,&g,0)||fabsf(g-p[1])>5.f){noGround++;continue;}
   Car c;carInit(&c,0,&w,x,g,z,h);CarInput in={0};for(int j=0;j<15;j++)carUpdate(&c,&w,&in,1.f/60);
   carSetSpeed(&c,si?20.f*si/3.6f:0.f);in.throttle=1;
   float still=0,peakstill=0,anchorx=c.x,anchorz=c.z,along=0;int ok=0,hardtype=-1,hardid=-1,hardmat=-1;
   for(int fr=0;fr<600;fr++){
    carUpdate(&c,&w,&in,1.f/60);along=(c.x-p[0])*dx+(c.z-p[2])*dz;
    if(c.wallV>1.f){hardtype=c.wallType;hardid=c.wallIdx;hardmat=c.wallMat;}
    if(along>e+c.p.halfL+.25f){ok=1;break;}
    if(hypotf(c.x-anchorx,c.z-anchorz)>.5f){anchorx=c.x;anchorz=c.z;still=0;}else still+=1.f/60;
    peakstill=fmaxf(peakstill,still);if(still>3.f)break;
   }
   total++;passed+=ok;stuck+=!ok;
   printf("%d,%u,%.4f,%.4f,%d,%d,%d,%s,%.3f,%.3f,%d,%d,%d\n",typ,i,p[0],p[2],di,si*20,si==0,ok?"PASS":"CANDIDATE",along,peakstill,hardtype,hardid,hardmat);
  }
 }
 fprintf(stderr,"objects=%d trials=%d pass=%d candidates=%d no_ground=%d\n",objects,total,passed,stuck,noGround);colFree(&w);free(b);return 0;
}
