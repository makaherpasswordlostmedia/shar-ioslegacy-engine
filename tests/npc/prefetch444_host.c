/* №444: calls the actual static ambSlots/modelFor/animFor of msn_view.c.
 * Real level mission NPC placements and real CHR1 loads; swept positions at
 * 120 km/h isolate streaming from road obstacles (not a physics-route claim).
 * No GPU is used. PSP I/O clock + memalign/blackbox are POSIX adapters only.
 */
#include "../../viewer/msn_view.c"
#include "world.h"
#include <time.h>
void *memalign(size_t alignment,size_t n){void*p=0;return posix_memalign(&p,alignment,n)?0:p;}
unsigned sceKernelGetSystemTimeLow(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (unsigned)((unsigned long long)t.tv_sec*1000000+t.tv_nsec/1000);}
void bbOp(const char *op,const char *arg,int sync){(void)op;(void)arg;(void)sync;}
static BotWorld W;
static unsigned maxBytes;static int maxModels,maxAnims,fail,checks;
static void clearModels(void){for(int k=0;k<NMODEL;k++)if(model[k].m)dropModel(k);ambElapsed=0;}
static void accounting(void){unsigned bytes=0;int models=0,anims=0;for(int k=0;k<NMODEL;k++)if(model[k].m){bytes+=model[k].m->h->size+sizeof(SkinModel);models++;}for(int k=0;k<NANIM;k++)if(anim[k]){bytes+=sizeof(NpcAnim);anims++;}if(bytes>maxBytes)maxBytes=bytes;if(models>maxModels)maxModels=models;if(anims>maxAnims)maxAnims=anims;}
int main(int argc,char**argv){
 if(argc!=5)return 2;setvbuf(stdout,NULL,_IONBF,0);
 if(bwData(argv[1],argv[2],argv[3])||bwNew(&W))return 2;
 M=W.msn;snprintf(dir,sizeof dir,"%s/",argv[4]);
 for(int mi=0;mi<(int)M.f.nmissions;mi++){
  const char *id=msn_str(&M.f,M.f.missions[mi].id);
  if(!id||strncmp(id,"sr",2))continue;
  int target=-1;for(int i=0;i<M.nnpc;i++)if(M.npc[i].bonus==mi+1)target=i;
  if(target<0){printf("FAIL L%d %s missing live race NPC\n",bwLevel(),id);fail++;continue;}
  const GameNpc*n=&M.npc[target];
  printf("RACE L%d %s %s %.6f %.6f %.6f\n",bwLevel(),id,n->name,n->pos.x,n->pos.y,n->pos.z);
  // Include approaches from all compass directions, both render frequencies
  // and queue phases: nearest-model competition is actual, not a fake skin.
  for(int hz=30;hz<=60;hz+=30)for(int angle=0;angle<8;angle++)for(int phase=0;phase<2;phase++){
   clearModels();ambElapsed=phase ? NPC_PREFETCH_PERIOD*.9f : 0;
   float dt=1.f/hz,speed=120.f/3.6f,a=angle*3.14159265f/4,first=-1;int at80=0;
   for(float dist=200;dist>=65;dist-=speed*dt){
    float x=n->pos.x+sinf(a)*dist,z=n->pos.z+cosf(a)*dist;
    ambSlots(x,n->pos.y,z,8.f,speed,dt);accounting();
    NpcAnim*ready=animFor(npcKey(n),0,0);
    if(ready&&first<0)first=dist;
    if(dist<=NPC_DRAW_DISTANCE+8.f){at80=ready!=0;break;}
   }
   int ok=at80;checks++;fail+=!ok;
   printf("CHECK L%d %s %s hz%d angle%d phase%d model_ready=%.2fm eye_boundary=88m %s\n",bwLevel(),id,n->name,hz,angle,phase,first,ok?"PASS":"FAIL");
  }
 }
 printf("CACHE max_bytes=%u models=%d/%d anims=%d/%d\n",maxBytes,maxModels,NMODEL,maxAnims,NANIM);
 printf("RESULT L%d %s checks=%d fail=%d\n",bwLevel(),fail?"FAIL":"PASS",checks,fail);clearModels();return fail||checks!=96?1:0;
}
