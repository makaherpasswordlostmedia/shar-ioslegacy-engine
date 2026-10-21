/* Real game/mission/shop runtime. Disk expectations are supplied independently by gate.py.
   Completion injection tests reward dispatch, not mission traversal. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
static int fail;
static void ck(const char *what, const char *name, int ok) { printf("CHECK %s %s %s\n", what,name,ok?"PASS":"FAIL"); fail += !ok; }
static void finish(int mi) {
 MsnRuntime *rt=&W.msn.rt; const MsnFile *f=&W.msn.f;
 const MsnPhase *ph=&f->phases[f->missions[mi].main];
 rt->cur=mi; rt->phase=1; rt->stage=ph->stage_count-1;
 rt->st=&f->stages[ph->first_stage+rt->stage]; rt->status=MSN_BETWEEN; rt->delay=0;
 MsnWorld w; memset(&w,0,sizeof w); msn_tick(rt,.01f,&w);
 ck("completion",msn_str(f,f->missions[mi].id),!!(rt->completed&(1u<<mi)));
}
int main(int argc,char **argv) {
 if(argc!=6) return 2;
 if(bwData(argv[1],argv[2],argv[3])) return 3;
 bwNew(&W); for(int k=0;k<2;k++) bwStep(&W,0,0,0);
 Shop *s=&W.msn.shop;
 FILE *f=fopen(argv[4],"r"); if(!f) return 4;
 char nm[32],q[32],seller[32]; int price,n=0;
 while(fscanf(f,"%31s %31s %d %31s",nm,q,&price,seller)==4) {
  int it=shopFind(s,nm); ck("catalog",nm,it>=0&&s->item[it].kind==SHOP_CAR&&s->item[it].price==price&&strcmp(s->item[it].quest,q)==0);
  if(it<0) continue;
  ck("initial",nm,shopOwns(s,SHOP_CAR,nm)==(!strcmp(q,"defaultcar")));
  if(!strcmp(q,"forsale")) {
   int si=-1,sel=-1;
   for(int j=0;j<s->nseller;j++) if(!strcmp(s->seller[j].shop,seller)) si=j;
   if(si>=0) for(int j=0;j<shopSellerCount(s,si);j++) if(shopSellerItem(s,si,j)==it) sel=j;
   ck("seller",nm,si>=0&&sel>=0&&s->seller[si].hasCar);
   if(si<0||sel<0) continue;
   s->open=1;s->at=si;s->sel=sel;
   GamePad pad; memset(&pad,0,sizeof pad); pad.hit=GP_CROSS;
   W.coins.collected=price-1; unsigned d=W.msn.shopDenied;
   gameShopInput(&W.msn,&pad); ck("insufficient",nm,W.coins.collected==price-1&&!shopOwns(s,SHOP_CAR,nm)&&W.msn.shopDenied==d+1);
   W.coins.collected=price; gameShopInput(&W.msn,&pad);
   ck("purchase",nm,W.coins.collected==0&&shopOwns(s,SHOP_CAR,nm));
   W.coins.collected=123; d=W.msn.shopDenied; gameShopInput(&W.msn,&pad);
   ck("repeat",nm,W.coins.collected==123&&W.msn.shopDenied==d+1);
   s->open=0;
  } else if(!strcmp(q,"bonusmission")||!strcmp(q,"streetrace")) {
   int races=0;
   for(unsigned j=0;j<W.msn.f.nmissions;j++) {
    unsigned flags=W.msn.f.missions[j].flags;
    if((!strcmp(q,"bonusmission")&&(flags&MSN_MF_BONUSMISSION))||(!strcmp(q,"streetrace")&&(flags&MSN_MF_STREETRACE)&&!(flags&MSN_MF_NOSCRIPT))) {
     finish(j); races++;
     if(!strcmp(q,"streetrace")&&races<3) ck("race-still-locked",nm,!shopOwns(s,SHOP_CAR,nm));
    }
   }
   ck("reward",nm,shopOwns(s,SHOP_CAR,nm));
   if(!strcmp(q,"streetrace")) ck("race-count",nm,races==3);
  }
  if(strcmp(q,"defaultcar")) ck("summon",nm,gameMsnPhoneCar(&W.msn,nm));
  n++;
 }
 fclose(f); ck("car-count","disk",n==6);
 f=fopen(argv[5],"r"); if(!f)return 5;
 float radius;
 while(fscanf(f,"%31s %31s %f",seller,nm,&radius)==3) {
  int si=-1; for(int j=0;j<s->nseller;j++) if(!strcmp(s->seller[j].shop,seller))si=j;
  ck("seller-disk",seller,si>=0&&!strcmp(s->seller[si].npc,nm)&&fabsf(s->seller[si].radius-radius)<.001f);
 }
 fclose(f);
 printf("RESULT L%d %s fails=%d\n",s->level,fail?"FAIL":"PASS",fail);
 return !!fail;
}
