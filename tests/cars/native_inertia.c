// Exercise the actual solver's tensor response, not a second implementation.
#include <stdio.h>
#include "../../viewer/car.c"
int main(void) {
  for (unsigned k=0;k<sizeof carBodyPhysics/sizeof *carBodyPhysics;k++) {
    const char *name=carBodyPhysics[k].name; Car c; memset(&c,0,sizeof c);
    if (!carParamsFor(name,&c.p)) return 2; derive(&c);
    for (int shape=0;shape<4;shape++) {
    float comp[4];for(int j=0;j<4;j++)comp[j]=shape==0?c.eq:shape==1?0.f:shape==2?c.lim:c.lim*(j+1)/4.f;
    updateBodyTensor(&c,comp);
    printf("%s %.9g %.9g",name,(double)c.p.mass,(double)bodyMass(&c));
    for(int j=0;j<4;j++)printf(" %.9g",(double)comp[j]);
    for (int j=0;j<6;j++) printf(" %.9g",(double)c.bodyTensor[j]);
    for (int j=0;j<6;j++) printf(" %.9g",(double)c.invInertia[j]);
    for (int pose=0;pose<4;pose++) {
      c.q[0]=1.f;c.q[1]=.11f*pose;c.q[2]=-.07f*pose;c.q[3]=.03f*pose;quatNorm(c.q);
      M3 M=quatM(c.q);V3 a=invIw(&c,&M,v3(7.f,-3.f,11.f));
      for(int j=0;j<4;j++)printf(" %.9g",(double)c.q[j]);
      printf(" %.9g %.9g %.9g",(double)a.x,(double)a.y,(double)a.z);
    }
    printf("\n");
    }
  }
  return 0;
}
