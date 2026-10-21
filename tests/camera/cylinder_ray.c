#include <stdio.h>
#include <math.h>
#include <string.h>
#include "col.h"
static struct {ColHdr h;ColCyl cyl;unsigned start[2],ref;} data;
static int cases,bad;
static void check(ColWorld*w,const char*label,float a[3],float b[3],float want){
 float got=colRayFrac(w,a,b,0);cases++;if(fabsf(got-want)>2.e-5f){bad++;printf("FAIL %s got=%g want=%g\n",label,got,want);}
}
#define RAY(label,x,y,z,xx,yy,zz,t) check(&w,label,(float[3]){x,y,z},(float[3]){xx,yy,zz},t)
int main(void){
 memset(&data,0,sizeof data);memcpy(data.h.magic,"COL1",4);data.h.ox=data.h.oz=-20;data.h.cell=40;data.h.W=data.h.H=1;data.h.ncyl=data.h.nref=1;data.start[1]=1;data.ref=2u<<29;
 data.cyl=(ColCyl){{0,0,0},{1,0,0},1,2,1,{0,0,0}};ColWorld w;if(colInit(&w,&data,sizeof data))return 2;
 RAY("space beyond flat end",2.5,-2,0,2.5,2,0,1);
 RAY("axial entry through flat cap",4,0,0,0,0,0,.5);
 RAY("side of barrel",0,3,0,0,-3,0,1.f/3);
 RAY("miss radially",4,2,0,-4,2,0,1);
 RAY("short segment before cap",4,0,0,3,0,0,1);
 RAY("origin inside ignored",0,0,0,4,0,0,1);
 RAY("beyond cap is outside, not capsule inside",2.5,0,0,0,0,0,.2);
 RAY("zero length outside",4,0,0,4,0,0,1);
 RAY("tangent barrel",0,1,-2,0,1,2,.5);
 float s=sqrtf(.5f);data.cyl.axis[0]=data.cyl.axis[1]=s;
 RAY("inclined axial cap",4*s,4*s,0,0,0,0,.5);
 RAY("inclined radial barrel",-3*s,3*s,0,3*s,-3*s,0,1.f/3);
 data.cyl.axis[0]=data.cyl.axis[1]=-s;
 RAY("reversed axis same cap",4*s,4*s,0,0,0,0,.5);
 data.cyl=(ColCyl){{0,0,0},{0,1,0},1,2,1,{0,0,0}};
 RAY("vertical cap",0,4,0,0,0,0,.5);
 data.cyl.flat=0;RAY("actual capsule remains rounded",0,4,0,0,0,0,.25);
 data.cyl.halfLen=0;RAY("zero height stays sphere",0,4,0,0,0,0,.75);
 data.cyl.r=0;RAY("disabled shape not a point",0,4,0,0,-4,0,1);
 colFree(&w);printf("%s camera cylinder ray cases=%d failures=%d\n",bad?"FAIL":"PASS",cases,bad);return !!bad;
}
