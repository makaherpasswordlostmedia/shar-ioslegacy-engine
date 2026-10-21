// Actual carvis/car/col; capture submitted GE mesh and state for all authored cars.
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <pspgu.h>
#include "carvis.h"
#include "carparams.h"
static int dither=1, texture, alphaTest, bias, draws, badState, queries;
static struct {unsigned c;float x,y,z;} mesh[16];
int sceGuGetStatus(int state){return state==GU_DITHER?dither:0;}
void sceGuDepthOffset(int value){bias=value;}
void sceGuDisable(int state){if(state==GU_DITHER)dither=0;if(state==GU_TEXTURE_2D)texture=0;if(state==GU_ALPHA_TEST)alphaTest=0;}
void sceGuEnable(int state){if(state==GU_DITHER)dither=1;if(state==GU_TEXTURE_2D)texture=1;if(state==GU_ALPHA_TEST)alphaTest=1;}
void sceGuDrawArray(int a,int b,int count,const void *indices,const void *vertices){
 (void)a;(void)b;(void)indices;if(count!=54)return;
 memcpy(mesh,vertices,sizeof mesh);draws++;badState+=!!dither+!!texture+!!alphaTest+(bias!=4);
}
int colGroundActual(const ColWorld*,float,float,float,float,float*,float*);
int colGround(const ColWorld*w,float x,float z,float top,float bottom,float*y,float*n){queries++;return colGroundActual(w,x,z,top,bottom,y,n);}
static struct {ColHdr h;ColTri tri[2];ColBox box;unsigned start[2],refs[3];} data;
static int failures;
#define CHECK(c) do{if(!(c)){failures++;if(failures<8)printf("FAIL line %d: %s\n",__LINE__,#c);}}while(0)
static float coplanar(void){
 float ax=mesh[3].x-mesh[0].x,ay=mesh[3].y-mesh[0].y,az=mesh[3].z-mesh[0].z;
 float bx=mesh[12].x-mesh[0].x,by=mesh[12].y-mesh[0].y,bz=mesh[12].z-mesh[0].z;
 float nx=ay*bz-az*by,ny=az*bx-ax*bz,nz=ax*by-ay*bx,nn=sqrtf(nx*nx+ny*ny+nz*nz),worst=0;
 for(int i=0;i<16;i++){float d=fabsf(nx*(mesh[i].x-mesh[0].x)+ny*(mesh[i].y-mesh[0].y)+nz*(mesh[i].z-mesh[0].z))/nn;if(d>worst)worst=d;}
 return worst;
}
int main(void){
 memcpy(data.h.magic,"COL1",4);data.h.ox=data.h.oz=-200;data.h.cell=400;data.h.W=data.h.H=1;data.h.ntri=2;data.h.nbox=1;data.h.nref=3;
 data.tri[0]=(ColTri){{-200,0,-200},{200,0,200},{200,0,-200},{0,1,0}};
 data.tri[1]=(ColTri){{-200,0,-200},{-200,0,200},{200,0,200},{0,1,0}};
 // Low curb overlaps some corners, not the centre; old mesh picks two supports.
 data.box=(ColBox){{3,-.4f,0},{1,0,0},{0,1,0},{0,0,1},{2,.6f,100},0};
 data.start[1]=3;data.refs[1]=1;data.refs[2]=COL_BOX<<29;
 ColWorld world;CHECK(!colInit(&world,&data,sizeof data));
 int fleet=0;float worstPlane=0,worstStep=0;
 for(int j=0;j<CAR_CONS;j++){
  CarParams p;if(!carParamsFor(carCons[j].name,&p))continue;fleet++;
  Car car;carInit(&car,&p,&world,0,.5f,0,0);car.grounded=1;car.wheels=4;
  CarVis vis={0};vis.ok=1;vis.wheelRad=p.wheelRad;carVisReset(&vis);
  queries=0;draws=0;badState=0;carVisDrawShadow(&vis,&car,&world);CHECK(draws==1);
  CHECK(queries<=1);CHECK(dither==1 && bias==0);unsigned char first[sizeof mesh];memcpy(first,mesh,sizeof mesh);
  for(int i=0;i<120;i++){car.y=.5f+((i%4)*.005f);carVisDrawShadow(&vis,&car,&world);CHECK(!memcmp(first,mesh,sizeof mesh));}
  CHECK(queries<=1);CHECK(!badState);
  // Straight/turn, cross the curb without splitting the shadow into other planes.
  float prevY=mesh[5].y;car.vel[0]=3;CarInput in={0};
  for(int i=0;i<120;i++){
   car.x=i*.03f;car.h=i*.003f;car.q[0]=cosf(car.h*.5f);car.q[2]=sinf(car.h*.5f);
   carVisUpdate(&vis,&car,&in,1.f/60);queries=0;carVisDrawShadow(&vis,&car,&world);
   float plane=coplanar(),step=fabsf(mesh[5].y-prevY);prevY=mesh[5].y;
   if(plane>worstPlane)worstPlane=plane;if(step>worstStep)worstStep=step;
   CHECK(plane<.00001f);CHECK(step<.04f);CHECK(queries<=1);CHECK(!badState);CHECK(dither==1);
   unsigned alpha=mesh[5].c>>24;CHECK(alpha>0 && alpha<255);CHECK(mesh[6].c==mesh[5].c && mesh[9].c==mesh[5].c && mesh[10].c==mesh[5].c);
   for(int k=0;k<16;k++)if(k/4==0||k/4==3||k%4==0||k%4==3)CHECK(!(mesh[k].c>>24));
  }
  // Teleport snaps to the real new receiver; flight fades, reset removes stale plane.
  car.x=30;carVisDrawShadow(&vis,&car,&world);CHECK(fabsf(mesh[5].y-.05f)<.00001f);
  car.grounded=0;car.y=6;car.vel[1]=1;
  for(int i=0;i<120;i++)carVisDrawShadow(&vis,&car,&world);
  CHECK((mesh[5].c>>24)<40);carVisReset(&vis);CHECK(!vis.shadowValid);
 }
 // A real sloped receiver remains a plane under a changing car heading.
 data.box.c[0]=150;data.box.c[2]=150;data.box.h[2]=2;
 for(int i=0;i<2;i++){
  float *v[3]={data.tri[i].a,data.tri[i].b,data.tri[i].c};
  for(int k=0;k<3;k++)v[k][1]=v[k][0]*.15f;
  data.tri[i].n[0]=-.15f/sqrtf(1.0225f);data.tri[i].n[1]=1.f/sqrtf(1.0225f);
 }
 colFree(&world);CHECK(!colInit(&world,&data,sizeof data));
 Car c;CarParams p;carDefaults(&p);carInit(&c,&p,&world,0,.5f,0,0);c.vel[0]=2;c.grounded=1;
 CarVis v={0};v.ok=1;v.wheelRad=p.wheelRad;carVisReset(&v);
 for(int i=0;i<120;i++){c.x=i*.03f;c.y=.5f+c.x*.15f;carVisDrawShadow(&v,&c,&world);CHECK(coplanar()<.00001f);CHECK(fabsf(mesh[5].y-(mesh[5].x*.15f+.05f))<.00001f);}
 c.x=250;carVisDrawShadow(&v,&c,&world);CHECK(!v.shadowValid);
 colFree(&world);printf("%s fleet=%d failures=%d planeError=%.9g frameStep=%.9g (m)\n",failures?"FAIL":"PASS",fleet,failures,worstPlane,worstStep);return !!failures;
}
