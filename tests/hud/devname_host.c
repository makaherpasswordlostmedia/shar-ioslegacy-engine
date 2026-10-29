#define SHAR_RELEASE 1
#define SHAR_RELEASE_KEEP_DIAG 1
#define SHAR_RELEASE_KEEP_HUD 1
#include <stdio.h>
#include "release.h"   /* cc -I viewer -o t tests/hud/devname_host.c && ./t */
int main(void){
  const char *lock[]={"acct","acctoff","acct.txt","loadacc","bisect","groundbias","pausecellold","startnoloadold","uifit.txt"};
  const char *free_[]={"mecityoff","startnewsold","newsiris","coneold","homerspotold","homerlitold","hudon","loadsilent","regprehyst","far_plain","fontcredit.txt","blackbox.txt"};
  int bad=0;
  for(unsigned i=0;i<sizeof lock/sizeof*lock;i++) if(!shrDevName(lock[i])){printf("НЕ ЗАПЕРТ %s\n",lock[i]);bad++;}
  for(unsigned i=0;i<sizeof free_/sizeof*free_;i++) if(shrDevName(free_[i])){printf("ЗАПЕРТ %s\n",free_[i]);bad++;}
  puts(bad?"FAIL":"PASS"); return bad;}
