#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "audio.h"
int main(int argc,char **argv){
 if(argc!=3)return 2;if(audioInit(argv[1])<0)return 2;
 int id=audioFind("siren");if(id<0){puts("FAIL absent native siren");audioShutdown();return 1;}
 for(int i=0;i<AUDIO_NBUS;i++){audioBus(i,1);audioUserVolume(i,1);}audioMaster(1);
 audioListener(0,0,0,1,0);float z=atof(argv[2]);
 int h=audioPlayAtGain(id,1,0,0,z,80,250);if(!h&&z<250)return 1;
 short b[1024];double energy[6]={0};
 for(int sec=0;sec<6;sec++)for(int k=0;k<86;k++){
  audioHostMix(b,512);for(int j=0;j<1024;j++)energy[sec]+=(double)b[j]*b[j];
 }
 printf("PCM");for(int i=0;i<6;i++)printf(" %.12g",sqrt(energy[i]/(86*1024))/32768.);puts("");
 int live=audioPlaying(h);audioStop(h);for(int k=0;k<8;k++)audioHostMix(b,512);
 double tail=0;for(int j=0;j<1024;j++)tail+=(double)b[j]*b[j];
 printf("LIVE %d STOP %.12g\n",live,tail);audioShutdown();return (z<250&&!live)||tail!=0;
}
