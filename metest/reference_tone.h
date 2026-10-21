#pragma once
#define REF_TONE_SAMPLES 441
// Four cycles per 441 samples = 400 Hz at 44100 Hz; phase survives packet boundaries.
// Crossfade source selection over 128 samples, never introduce a hard switch.
static void refToneMix(short *out,const int *engine,const short *table,unsigned *phase,
                       unsigned *blend,int tone,int gl,int gr,unsigned *clips,unsigned *peak){
  for(unsigned i=0;i<512;i++){
    if(tone&&*blend<128)(*blend)++;else if(!tone&&*blend)(*blend)--;
    int t=table[*phase];*phase=(*phase+1)%REF_TONE_SAMPLES;
    int gain[2]={gl,gr};
    for(unsigned c=0;c<2;c++){
      int s=(int)(((long long)engine[i*2+c]*(128-*blend)+(long long)t*gain[c]/32768*(*blend))/128);
      *clips+=s>32767||s<-32768;out[i*2+c]=(short)(s>32767?32767:s<-32768?-32768:s);
      unsigned a=out[i*2+c]<0?-(int)out[i*2+c]:out[i*2+c];if(a>*peak)*peak=a;
    }
  }
}
