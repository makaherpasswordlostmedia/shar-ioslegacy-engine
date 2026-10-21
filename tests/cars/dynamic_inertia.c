// Suspension changes inertia without an external angular impulse. Exercise
// the production transition and check world momentum in double precision.
#include <stdio.h>
#include "../../viewer/car.c"
static void momentum(const Car*c,const M3*M,V3 omega,double L[3]) {
 const float*t=c->bodyTensor;double I[3][3]={{t[0],t[1],t[2]},{t[1],t[3],t[4]},{t[2],t[4],t[5]}};
 double R[3][3]={{M->L.x,M->U.x,M->F.x},{M->L.y,M->U.y,M->F.y},{M->L.z,M->U.z,M->F.z}};
 double v[3]={omega.x,omega.y,omega.z},local[3]={0},lb[3]={0};
 for(int i=0;i<3;i++)for(int j=0;j<3;j++)local[i]+=R[j][i]*v[j];
 for(int i=0;i<3;i++)for(int j=0;j<3;j++)lb[i]+=I[i][j]*local[j];
 for(int i=0;i<3;i++){L[i]=0;for(int j=0;j<3;j++)L[i]+=R[i][j]*lb[j];}
}
int main(void) {
 int cases=0,bad=0;double worst=0;
 for(unsigned k=0;k<sizeof carBodyPhysics/sizeof *carBodyPhysics;k++)for(int pose=0;pose<4;pose++) {
  Car c;memset(&c,0,sizeof c);if(!carParamsFor(carBodyPhysics[k].name,&c.p))return 2;derive(&c);
  c.q[0]=1;c.q[1]=.11f*pose;c.q[2]=-.07f*pose;c.q[3]=.03f*pose;quatNorm(c.q);M3 M=quatM(c.q);
  V3 omega=v3(.8f,-.4f,1.7f);double expected[3];momentum(&c,&M,omega,expected);
  for(int shape=0;shape<4;shape++) {
   float comp[4];for(int i=0;i<4;i++)comp[i]=shape==0?0.f:shape==1?c.lim:shape==2?c.lim*(i+1)/4.f:c.eq;
   omega=changeBodyTensor(&c,&M,comp,omega);double got[3];momentum(&c,&M,omega,got);
   double error=0,norm=0;for(int i=0;i<3;i++){error+=(got[i]-expected[i])*(got[i]-expected[i]);norm+=expected[i]*expected[i];}
   error=sqrt(error/norm);if(error>worst)worst=error;cases++;
   if(!isfinite(error)||error>1e-5){bad++;if(bad<=5)printf("FAIL %s pose%d shape%d relative angular impulse %.9g\n",carBodyPhysics[k].name,pose,shape,error);}
  }
 }
 printf("%s %d transitions; %d bad; worst relative angular impulse %.9g\n",bad?"FAIL":"PASS",cases,bad,worst);return !!bad;
}
