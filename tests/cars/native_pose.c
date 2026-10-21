// Actual runtime parameters (including CAR1 legacy fields) against original RAM.
#include <stdio.h>
#include "../../viewer/car.c"
int main(int argc,char **argv) {
  if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  unsigned char h[104];if(fread(h,1,sizeof h,f)!=sizeof h)return 2;
  unsigned co;memcpy(&co,h+100,4);if(fseek(f,co,SEEK_SET))return 2;
  unsigned char sec[8192];size_t size=fread(sec,1,sizeof sec,f);fclose(f);
  Car c;memset(&c,0,sizeof c);if(carParamsFromCar1(sec,size,&c.p)!=1)return 2;derive(&c);
  float storedLift;memcpy(&storedLift,sec+32,4);float origin=carModelLift(&c,storedLift);
  printf("%s radius %.9g eq %.9g origin %.9g centre %.9g %.9g %.9g\n",c.p.name,(double)c.p.wheelRad,(double)c.eq,
    (double)origin,(double)c.comBase[0],(double)(c.comBase[1]-origin),(double)c.comBase[2]);
}
