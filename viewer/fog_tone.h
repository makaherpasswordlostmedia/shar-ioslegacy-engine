#ifndef SHAR_FOG_TONE_H
#define SHAR_FOG_TONE_H
#include <math.h>
static inline unsigned fogTone(float r,float g,float b,float luminance,float saturation,int old) {
  float L=.30f*r+.59f*g+.11f*b, gray=L*luminance;
  if(old)gray=fminf(.58f,fmaxf(.42f,gray)); // previous shared brightness floor, including night levels
  float channels[3]={r,g,b}; unsigned out=0;
  for(int k=0;k<3;k++) {
    float c=gray+(channels[k]-L)*saturation;
    unsigned q=(unsigned)(fminf(1.f,fmaxf(0.f,c))*255.f+.5f);out|=q<<(8*k);
  }
  return out;
}
#endif
