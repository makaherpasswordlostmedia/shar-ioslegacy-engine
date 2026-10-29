#include <stdio.h>
#include <string.h>
#include "../../viewer/sound.c"
static int live[32],next=1,plays,sets,stops;
int audioPlaying(int h){return h>0&&h<32&&live[h];}
int audioPlayAtGain(int id,float gain,float x,float y,float z,float mn,float mx){int h=next++;if(h>=32)return 0;live[h]=1;plays++;printf("PLAY %d %.9g %.9g %.9g %.9g %.9g %.9g\n",id,gain,x,y,z,mn,mx);return h;}
void audioSetAt(int h,float x,float y,float z,float mn,float mx){sets++;printf("MOVE %d %.9g %.9g %.9g %.9g %.9g\n",h,x,y,z,mn,mx);}
void audioStop(int h){if(audioPlaying(h)){stops++;live[h]=0;printf("STOP %d\n",h);}}
const char *audioSoundName(int id){return "siren";}
int main(void){
 ready=1;rSiren=5;MsnCars cars={0};cars.n=2;
 for(int i=0;i<2;i++){cars.c[i].on=cars.c[i].police=1;cars.c[i].car.x=10+i;cars.c[i].car.ry=2;cars.c[i].car.z=30+i;}
 sndPoliceCars(&cars);sndPoliceCars(&cars);if(plays!=2||sets!=2)return 1;
 cars.c[0].car.x=15;cars.c[1].car.destroyed=1;sndPoliceCars(&cars);if(sets!=3||stops!=1)return 1;
 sndPoliceCars(NULL);if(stops!=2)return 1;
 rSiren=-1;sndPoliceCars(&cars);if(plays!=2)return 1;
 printf("PASS pool=2 position updates=3 complete cleanup=2 absent bank silent\n");return 0;
}
