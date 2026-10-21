// Actual carVisUpdate on disc-authored hinges: frame rate cannot freeze force during substeps.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "hinge_fixture.h"
int main(int argc,char **argv){
 CarVis original;if(!hingeFixture(&original,argc>1?argv[1]:"build/ship_stage/level.shr")||original.nhinge!=4)return 2;
 Car c={0};carDefaults(&c.p);c.q[0]=1;c.damage=.8f;original.prevDamage=c.damage;
 int bad=0,checks=0;float worst=0;
 for(int setting=0;setting<4;setting++) {
  CarVis refs=original;
  for(int j=0;j<refs.nhinge;j++){refs.latched[j]=0;refs.th[j]=refs.hinge[j].max*.2f*(setting+1);refs.thv[j]=(setting-2)*2;}
  for(int hz=30;hz<=60;hz*=2){CarVis got=refs,ref=refs;float error=0;
   for(int fr=0;fr<4*hz;fr++){
    carVisUpdate(&got,&c,0,1.f/hz);for(int step=0;step<120/hz;step++)carVisUpdate(&ref,&c,0,1.f/120);
    for(int j=0;j<got.nhinge;j++){float e=fabsf(got.th[j]-ref.th[j])+fabsf(got.thv[j]-ref.thv[j]);if(e>error)error=e;checks++;if(e>.0001f)bad++;}
   }
   if(error>worst)worst=error;
  }
 }
 printf("%s native hinges=%d checks=%d inconsistent=%d worst angle+velocity %.9g\n",bad?"FAIL":"PASS",original.nhinge,checks,bad,worst);return !!bad;
}
