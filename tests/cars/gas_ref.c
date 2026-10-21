// Real car/level at the recorded state_l1_incar start; 60 PAL frames idle, 100 gas.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
#include "col.h"
int main(int argc,char **argv) {
  if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(fread(b,1,n,f)!=n)return 2;fclose(f);
  unsigned co=*(unsigned*)(b+92),po=*(unsigned*)(b+96),pv=*(unsigned*)(b+88),end=n;
  if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;
  ColWorld w;if(colInit(&w,b+co,end-co))return 2;CarParams p;carParamsFor("famil_v",&p);
#ifdef GAS_REF_OLD
  p.gasScale*=.5f;  // negative: incomplete acceleration transfer, same measured trajectory criterion
#endif
  float y;if(!colGround(&w,215.054f,170.248f,10,-10,&y,0))return 2;
  Car c;carInit(&c,&p,&w,215.054f,y,170.248f,3.14159265f+17.2f*.0174533f);
  for(int i=0;i<160;i++){CarInput in={0};in.throttle=i>=60;carUpdate(&c,&w,&in,1.f/50);}
  printf("%.9g\n",hypotf(c.vel[0],c.vel[2]));colFree(&w);free(b);return 0;
}
