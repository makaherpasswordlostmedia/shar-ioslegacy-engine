// A cache model of the actual kernel result publisher and the caller's invalidate
#include <stdio.h>
#include <string.h>
#include "../viewer/me/mebox.h"
static MeSvcRes cache,ram;static int red,writes;
static void writeback(const void *p,unsigned size){
  if(p!=&cache||size!=sizeof cache)return;
  if(!red){memcpy(&ram,p,size);writes++;}
}
static int valid(const MeSvcRes *r){return r->magic==ME_SVC_MAGIC&&r->kick&&r->quiesce&&r->poll&&r->stage==3&&r->table==2&&r->init==0;}
int main(int argc,char **argv){
  (void)argv;red=argc>1;int fail=0;
  for(unsigned i=0;i<1000;i++){
    // Earlier incidental flush: exactly the symptom reported, stage=3/init=0,
    // final entry points/signature still dirty when caller invalidates
    memset(&ram,0,sizeof ram);ram.stage=3;ram.table=2;cache=ram;
    cache.kick=0x88001000+i*4;cache.quiesce=0x88002000;cache.poll=0x88003000;
    MeSvcRes broken=ram;if(valid(&broken))return 2;
    meSvcPublish(&cache,writeback);
    cache=ram; // caller's invalidate: throw away dirty cache, read RAM
    fail+=!valid(&cache);
  }
  printf("%s boot-publication cases=1000 failures=%d writebacks=%d negative=%d\n",fail?"FAIL":"PASS",fail,writes,red);
  return fail?1:0;
}
