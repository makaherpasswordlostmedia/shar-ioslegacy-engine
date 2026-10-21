// Actual car/col/skid, all authored car profiles and all seven level lifetimes.
#include "car.h"
#include "carparams.h"
#include "skid.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
static ColWorld W;static unsigned char *cm;static int bad;
static int load(const char *fn,float start[4]){
 FILE*f=fopen(fn,"rb");if(!f)return 1;unsigned char h[104];if(fread(h,1,104,f)!=104)return 1;
 memcpy(start,h+36,16);unsigned po=*(unsigned*)(h+88),co=*(unsigned*)(h+92),pr=*(unsigned*)(h+96);fseek(f,0,SEEK_END);unsigned end=ftell(f);if(po>co&&po<end)end=po;if(pr>co&&pr<end)end=pr;
 cm=aligned_alloc(64,(end-co+63)&~63u);fseek(f,co,SEEK_SET);if(fread(cm,1,end-co,f)!=end-co)return 1;fclose(f);return colInit(&W,cm,end-co);
}
int main(int n,char**v){if(n<3)return 2;int lv=atoi(v[2]);float st[4];if(load(v[1],st))return 2;printf("level\tcar\thover\tcontact_frames\tquad\tvisible\tresult\n");
 for(int i=0;i<CAR_CONS;i++){
  const char*name=carCons[i].name;CarParams p;if(!carParamsFor(name,&p))return 2;Car c;carInit(&c,&p,&W,st[0],st[1],st[2],st[3]);
  for(int f=0;f<30;f++){CarInput in={0};carUpdate(&c,&W,&in,1.f/60);}
  skidBeginLevel(lv);carSetSpeed(&c,20);int contact=0;
  for(int f=0;f<120;f++){CarInput in={0,0,1,1};carUpdate(&c,&W,&in,1.f/60);skidCar(0,&c,&in,&W);contact+=c.wheels>0;}
  SkidStat s;skidGetStat(&s);int visible=0;float pt[4][3];unsigned char a[4];
  for(int q=0;q<SKID_QUADS;q++)if(skidQuadAt(q,pt,a))for(int k=0;k<4;k++)visible+=a[k]>0;
  int hover=skidHover(name);int ok=hover ? s.made==0&&visible==0 : contact>0&&s.made>0&&visible>0;bad+=!ok;
  printf("%d\t%s\t%d\t%d\t%d\t%d\t%s\n",lv,name,hover,contact,s.made,visible,ok?"PASS":"FAIL");
 }
 printf("fleet443 L%d: %s (%d failures / %d profiles)\n",lv,bad?"FAIL":"PASS",bad,CAR_CONS);return bad?1:0;}
