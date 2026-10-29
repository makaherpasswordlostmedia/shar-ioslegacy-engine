#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "world.h"
#include "traffic.h"
#include "race_onroad.h"
#include "ui_anim.h"
static BotWorld W;
int main(int argc,char **argv) {
  if(argc!=4 || bwData(argv[1],argv[2],argv[3])) return 2;
  bwNew(&W); const Traffic *t=bwTraffic(); if(!t) return 3;
  unsigned samples=0,shortcuts=0; int fail=0; float maxx=-1e9f,maxz=-1e9f,maxw=0.f;
  for(unsigned r=0;r<t->hd->nRoad;r++) {
    const TrRoad *road=&t->road[r]; if(!road->lanes || road->nPt<2 || road->width<=0.f)continue;
    if(road->width>maxw)maxw=road->width;
    const TrPt *a=t->pt+road->firstPt,*b=a+(road->lanes-1)*road->nPt;
    for(unsigned k=1;k<road->nPt;k++) {
      float x=.25f*(a[k-1].x+b[k-1].x+a[k].x+b[k].x);
      float y=.25f*(a[k-1].y+b[k-1].y+a[k].y+b[k].y);
      float z=.25f*(a[k-1].z+b[k-1].z+a[k].z+b[k].z);
      samples++;shortcuts+=!!(road->flags&1);fail+=!raceOnRoad(t,x,y,z);
      float dx=a[k].x-a[k-1].x,dz=a[k].z-a[k-1].z,dl=hypotf(dx,dz);
      if(dl>0.f){float edge=road->width*road->lanes*.49f;
        fail+=!raceOnRoad(t,x-dz/dl*edge,y,z+dx/dl*edge);
        fail+=!raceOnRoad(t,x+dz/dl*edge,y,z-dx/dl*edge);}
      if(x>maxx)maxx=x;if(z>maxz)maxz=z;
    }
  }
  for(unsigned j=0;j<t->hd->nJunc;j++) {const TrJunc *q=&t->junc[j];if(q->x>maxx)maxx=q->x;if(q->z>maxz)maxz=q->z;if(q->r>maxw)maxw=q->r;}
  float ox=maxx+maxw*4.f,oz=maxz+maxw*4.f;
  fail+=raceOnRoad(t,ox,0.f,oz)!=0;
  /* Real bonus checkpoint setup, then actual frame tick; no injected completion. */
  int sr=-1;for(unsigned i=0;i<W.msn.f.nmissions;i++)if(!strcmp(msn_str(&W.msn.f,W.msn.f.missions[i].id),"sr2"))sr=i;
  if(sr<0)return 4;
  W.msn.rt.cp_phase=1;W.msn.rt.cp_stage=0;msn_start_mission(&W.msn.rt,sr,1);
  /* Authored countdown durations differ by level. Step until GO, never force status. */
  for(int f=0;f<3600&&W.msn.rt.status==MSN_COUNTDOWN;f++)bwStep(&W,0,0,0);
  fprintf(stderr,"fixture status=%d phase=%d stage=%d obj=%d items=%d nwp=%d cur=%d sr=%d\n",W.msn.rt.status,W.msn.rt.phase,W.msn.rt.stage,W.msn.rt.obj,W.msn.rt.nitems,W.msn.cars.nwp,W.msn.rt.cur,sr);
  const TrRoad *r=&t->road[0];const TrPt *a=t->pt+r->firstPt,*b=a+(r->lanes-1)*r->nPt;
  float x=.5f*(a[0].x+b[0].x),y=.5f*(a[0].y+b[0].y),z=.5f*(a[0].z+b[0].z);
  bwPlace(&W,x,y,z,0);bwStep(&W,0,0,0);
  int on=W.msn.racePlace>0&&!W.msn.raceOffRoad;fail+=!on;
  bwPlace(&W,ox,0.f,oz,0);bwStep(&W,0,0,0);
  int off=W.msn.racePlace>0&&W.msn.raceOffRoad;fail+=!off;
  char text[24];uiPosText(text,sizeof text,W.msn.raceOffRoad?-1:W.msn.racePlace,W.msn.raceRacers+1);
  fail+=text[0]!='?' || strstr(text," / ")!=NULL || !strstr(text,"/");
  printf("L%d %s samples=%u shortcuts=%u runtime_on=%d off=%d HUD=%s fails=%d\n",bwLevel(),fail?"FAIL":"PASS",samples,shortcuts,on,off,text,fail);
  return !!fail;
}
