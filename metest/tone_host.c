#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "reference_tone.h"
static short table[REF_TONE_SAMPLES],out[1024];static int engine[1024];
int main(int argc,char **argv){
  (void)argv;unsigned phase=0,blend=128,clips=0,peak=0,wrong=0,maxSeam=0;short previous=0;
  for(unsigned i=0;i<REF_TONE_SAMPLES;i++)table[i]=(short)(8192.f*sinf(25.13274122872f*i/REF_TONE_SAMPLES));
  for(unsigned block=0;block<1000;block++){
    if(argc>1)phase=0; // Broken producer resets the clean carrier on each packet
    refToneMix(out,engine,table,&phase,&blend,1,8192,8192,&clips,&peak);
    for(unsigned i=0;i<512;i++){
      short expect=(short)(table[(block*512+i)%REF_TONE_SAMPLES]/4);
      wrong+=out[i*2]!=expect||out[i*2+1]!=expect;
    }
    if(block){unsigned d=abs((int)out[0]-previous);if(d>maxSeam)maxSeam=d;}
    previous=out[1022];
  }
  int bad=wrong||clips||maxSeam>128;
  printf("%s clean-tone packets=1000 wrong=%u clipped=%u max-packet-step=%u peak=%u negative=%d\n",bad?"FAIL":"PASS",wrong,clips,maxSeam,peak,argc>1);return bad?1:0;
}
