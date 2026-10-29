// Check the actual suspension projection against independent 3D plane geometry.
#include <stdio.h>
#include "../../viewer/car.c"
int main(void) {
  int checks=0,bad=0;double worst=0;
  for(int model=0;model<CAR_CONS;model++) {
    CarParams p;if(!carParamsFor(carCons[model].name,&p))return 2;
    for(int roll=-60;roll<=60;roll+=15)for(int slope=-30;slope<=30;slope+=15)
      for(int distance=1;distance<=5;distance++) {
        double angle=roll*3.141592653589793/180,grade=slope*3.141592653589793/180;
        double up[3]={sin(angle),cos(angle),0},normal[3]={-sin(grade),cos(grade),0};
        double un=up[0]*normal[0]+up[1]*normal[1];if(un<.4)continue;
        double mount[3]={.3,.2+distance*.2,-.7};
        double dotMount=mount[0]*normal[0]+mount[1]*normal[1];
        float extension=suspensionExtension((float)dotMount,(float)un,p.wheelRad);
        double centre[3];for(int k=0;k<3;k++)centre[k]=mount[k]-up[k]*extension;
        // Signed centre-to-plane distance measured from the final 3D point.
        double error=fabs(centre[0]*normal[0]+centre[1]*normal[1]-p.wheelRad);
        if(error>worst)worst=error;checks++;
        if(!isfinite(error)||error>.000001) {
          bad++;if(bad<=5)printf("FAIL %s roll=%d slope=%d normal penetration=%.9g\n",p.name,roll,slope,error);
        }
      }
  }
  printf("%s %d tyre/plane checks; %d failures; max normal error %.9g m\n",bad?"FAIL":"PASS",checks,bad,worst);
  return !!bad;
}
