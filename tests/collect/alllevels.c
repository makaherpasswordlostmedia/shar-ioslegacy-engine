/* Disc expectations against live collect/coins/Game APIs; no renderer/PSP timing claims.
 * alllevels EXPECT PACK LEVEL HOMER [card|wasp|gag|coin|wrench]
 * Plants alter the loaded data, never the source/ship package. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "rooms.h"

static int fail, checks, level;
static unsigned gfxRooms;
static int canEnterGfx(void *unused,int room) { (void)unused;return !!(gfxRooms&(1u<<room)); }
static void check(const char *kind, const char *name, int ok, int got, int want) {
  printf("CHECK L%d %s %s %s got=%d want=%d\n",level,kind,name,ok?"PASS":"FAIL",got,want);
  checks++; if (!ok) fail++;
}
static void *readall(const char *path, size_t *size) {
  FILE *f=fopen(path,"rb"); if (!f) return NULL;
  fseek(f,0,SEEK_END); *size=ftell(f); rewind(f);
  void *p=aligned_alloc(16,(*size+15)&~(size_t)15);
  if (!p || fread(p,1,*size,f)!=*size) { fclose(f); free(p); return NULL; }
  fclose(f); return p;
}
typedef struct { char kind[10], name[64]; int room,trig,cycle,random,coins; float x,y,z,r; char fmv[16]; } Exp;
static Exp ex[2048]; static int nex;
static Collect c; static Coins loot;
static int step(float x,float y,float z,int room,int act,float dt,int type,int idx) {
  CollPlayer p={x,y,z,1,room,act}; collectStep(&c,&p,NULL,NULL,NULL,&loot,dt);
  CollEvent e; int n=0; while (collectPop(&c,&e)) n += e.type==type && (idx<0 || e.idx==idx);
  return n;
}
static int value(void) { int n=loot.collected; for(unsigned i=0;i<loot.n;i++) n+=loot.c[i].active; return n; }
static int near3(float a,float b,float d,float x,float y,float z) { return fabsf(a-x)+fabsf(b-y)+fabsf(d-z)<.002f; }
int main(int argc,char **argv) {
  if(argc<5) return 2;
  FILE *f=fopen(argv[1],"r"); if(!f) return 2;
  char line[512]; while(fgets(line,sizeof line,f)) {
    if(nex>=2048) return 2; Exp *e=&ex[nex];
    if(sscanf(line,"gag\t%63s\t%d\t%d\t%d\t%d\t%d\t%f\t%f\t%f\t%f\t%15s",e->name,&e->room,&e->trig,&e->cycle,&e->random,&e->coins,&e->x,&e->y,&e->z,&e->r,e->fmv)==11) strcpy(e->kind,"gag");
    else if(sscanf(line,"%9s\t%63s\t%f\t%f\t%f\t%f",e->kind,e->name,&e->x,&e->y,&e->z,&e->r)!=6) return 2;
    nex++;
  } fclose(f);
  size_t n; unsigned char *pak=readall(argv[2],&n); if(!pak) return 2;
  const char *plant=argc>5?argv[5]:""; unsigned *u=(unsigned *)(pak+4);
  if(!strcmp(plant,"card")) ((CollCard *)(pak+u[7]))[0].x+=20;
  if(!strcmp(plant,"wasp")) ((CollWasp *)(pak+u[9]))[0].x+=20;
  if(!strcmp(plant,"gag")) ((CollGag *)(pak+u[11]))[0].room=100;
  int rc=collectInit(&c,pak,n); if(rc) {fprintf(stderr,"collectInit: %d\n",rc);return 2;}
  level=c.level; coinsInit(&loot,NULL,0);
  int nc=0,nw=0,ng=0,ncg=0,gi=0; uint64_t mask=0;
  for(int k=0;k<nex;k++) { Exp *e=&ex[k];
    if(!strcmp(e->kind,"card")) {
      nc++; int id=atoi(e->name), idx=-1;
      for(unsigned i=0;i<c.ncard;i++) if(c.card[i].id==id) idx=i;
      int got=step(e->x,e->y-.9f,e->z,-1,0,1.f/60,CE_CARD,idx);
      check("card.pickup",e->name,idx>=0 && got==1 && c.st.cardGot[idx],got,1);
      check("card.once",e->name,step(e->x,e->y-.9f,e->z,-1,0,1.f/60,CE_CARD,idx)==0,0,0);
    }
  }
  int total,got=collectCount(&c,level,COLL_CARDS,&total);
  check("card.total","disc",nc==(int)c.ncard && got==nc && total==nc,got,nc);
  for(int k=0;k<nex;k++) { Exp *e=&ex[k]; if(strcmp(e->kind,"gag")) continue;
    int g=gi++; ng++; if(g>=(int)c.ngag) {check("gag.missing",e->name,0,0,1);continue;}
    const CollGag *G=&c.gag[g];
    check("gag.room",e->name,G->room==e->room,G->room,e->room);
    check("gag.metadata",e->name,!strcmp(G->name,e->name)&&G->trig==e->trig&&G->cycle==e->cycle&&G->coins==e->coins&&G->random==e->random&&fabsf(G->tr-e->r)<.002f&&near3(G->tx,G->ty,G->tz,e->x,e->y,e->z),G->coins,e->coins);
    if(!e->r) { check("gag.ambient","not_a_collectible",!e->coins,e->coins,0); continue; }
    collectNewGame(&c); collectSetProgress(&c,level,0,0,mask); coinsFree(&loot); coinsInit(&loot,NULL,0);
    int fired=0;
    for(int visit=0;visit<256&&!fired;visit++) {
      step(0,200,5000,-1,0,1.f/60,0,-1);
      step(e->x+e->r+1,e->y,e->z,e->room,0,1.f/60,0,-1);
      int far=step(e->x+e->r+.4f,e->y,e->z,e->room,1,1.f/60,CE_GAG_START,g);
      if(far) { check("gag.outside",e->name,0,far,0); break; }
      fired=step(e->x+.8f*e->r,e->y,e->z,e->room,e->trig,1.f/60,CE_GAG_START,g);
      if(!e->random) break;
    }
    check("gag.trigger",e->name,fired==1,fired,1);
    if(e->coins) {
      ncg++; float wait=fmaxf(G->len,G->coinDelay)+.5f;
      for(float t=0;t<wait;t+=1.f/60) step(e->x,e->y,e->z,e->room,0,1.f/60,0,-1);
      int v=value(); check("gag.coins",e->name,v==e->coins,v,e->coins);
      mask |= collectGags(&c,level);
      for(int t=0;t<3;t++) { step(e->x+e->r+1,e->y,e->z,e->room,0,.1f,0,-1); step(e->x,e->y,e->z,e->room,e->trig,.1f,0,-1); }
      check("gag.coins_once",e->name,value()==v,value(),v);
    }
  }
  check("gag.records","disc",ng==(int)c.ngag,ng,c.ngag);
  collectNewGame(&c); collectSetProgress(&c,level,0,0,mask);
  got=collectCount(&c,level,COLL_GAGS,&total); check("gag.total","disc",got==ncg&&total==ncg,got,ncg);
  uint32_t kills=0;
  for(int k=0;k<nex;k++) { Exp *e=&ex[k]; if(strcmp(e->kind,"wasp")) continue; nw++;
    int idx=-1; for(unsigned i=0;i<c.nwasp;i++) if(!strcmp(c.wasp[i].name,e->name))idx=i;
    if(idx<0) {check("wasp.missing",e->name,0,0,1);continue;}
    collectNewGame(&c);collectSetProgress(&c,level,0,kills,0);
    for(int t=0;t<3;t++) step(e->x+2,e->y-1.5f,e->z,-1,0,1.f/60,0,-1);
    SpRun *r=&c.sp.run[c.wasp[idx].inst];
    check("wasp.spawn",e->name,c.st.waspSt[idx]==1&&near3(r->x,r->y,r->z,e->x,e->y,e->z),c.st.waspSt[idx],1);
    int dead=0;
    for(int hit=0;hit<4&&!dead;hit++) {
      float v[3],rr;spBounds(&c.sp,c.wasp[idx].inst,v,&rr);
      HomerEvent he={HOMER_EV_HIT,v[0],v[1],v[2],1,0,1};collectHomerHit(&c,&he);
      for(int t=0;t<30;t++) dead+=step(e->x+2,e->y-1.5f,e->z,-1,0,1.f/60,CE_WASP_DEAD,idx);
    }
    check("wasp.kick",e->name,dead==1&&c.st.waspSt[idx]==2,dead,1); kills|=collectWasps(&c,level);
  }
  got=collectCount(&c,level,COLL_WASPS,&total);check("wasp.total","disc",got==nw&&total==nw,got,nw);
  static BotWorld W;
  if(bwData(argv[3],argv[4],NULL)||bwNew(&W)) return 2;
  check("world.collect","loaded",W.haveColl&&W.coll.level==level,W.haveColl,1);
  /* Validate the exact room files alongside LEVEL, including render data: the
   * PSP room-open callback refuses entry when the SHG1/RMG1 blob is absent. */
  char dir[1024],path[1200]; snprintf(dir,sizeof dir,"%s",argv[3]);
  char *slash=strrchr(dir,'/');if(slash) *slash=0;else strcpy(dir,".");
  snprintf(path,sizeof path,"%s/interiors-l%d.bin",dir,level);
  const char *roomOverride=getenv("COLLECT_ROOM_PACK");
  size_t rn=0;void *rp=readall(roomOverride?roomOverride:path,&rn);Rooms RR;
  if(!strcmp(plant,"rooms")) {free(rp);rp=NULL;rn=0;}
  int rrc=roomsParse(&RR,rp,rn);
  check("rooms.package","SHI1",rrc==0,rrc,0);
  snprintf(path,sizeof path,"%s/interiors-l%d-gfx.bin",dir,level);
  size_t gn=0;unsigned char *gb=readall(path,&gn);
  if(!strcmp(plant,"roomgfx")) {free(gb);gb=NULL;gn=0;}
  unsigned gnr=gb&&gn>=16?*(unsigned *)(gb+4):0;
  int gfxok=gb&&gn>=16&&!memcmp(gb,"SHG1",4)&&gnr<=ROOMS_MAX&&gn>=16+48*gnr;
  check("rooms.graphics","SHG1",gfxok,gfxok,1);
  if(!rrc) for(int ri=0;ri<RR.nroom;ri++) {
    int gid=collectRoomId(RR.room[ri].name),gfx=0,door=-1;
    if(gfxok) for(unsigned j=0;j<gnr;j++) {
      unsigned char *entry=gb+16+48*j;unsigned off=*(unsigned *)(entry+32),sz=*(unsigned *)(entry+36);
      if(!strcmp((char *)entry,RR.room[ri].name)&&off<=gn&&sz<=gn-off&&sz>=128&&!memcmp(gb+off,"RMG1",4)&&*(unsigned *)(gb+off+8)>0) gfx=1;
    }
    check("room.drawable",RR.room[ri].name,gfx,gfx,1);
    if(gfx) gfxRooms |= 1u<<ri;
    for(int di=0;di<RR.ndoor;di++) if(RR.door[di].room==ri) {door=di;break;}
    check("room.door",RR.room[ri].name,door>=0,door>=0,1);
    if(door>=0) {
      RoomState rs={0};roomStateInit(&rs);rs.needAction=1;rs.action=1;
      const RoomDoor *d=&RR.door[door];const float *pos=d->trig.kind>=0?d->trig.c:d->p;
      W.homer.state=HS_FOOT;W.homer.x=pos[0];W.homer.y=pos[1];W.homer.z=pos[2];
      int entered=roomsStep(&RR,&rs,&W.G,canEnterGfx,NULL);
      check("room.enter",RR.room[ri].name,entered==ROOM_EV_ENTER&&rs.room==ri&&collectRoomId(roomsName(&RR,&rs))==gid,entered,1);
      W.G.pHomerWorld=NULL;
    }
  }
  for(unsigned g=0;g<c.ngag;g++) if(c.gag[g].room>=0) {
    int found=0;if(!rrc) for(int ri=0;ri<RR.nroom;ri++) found+=collectRoomId(RR.room[ri].name)==c.gag[g].room;
    check("gag.room_delivered",c.gag[g].name,found==1,found,1);
  }
  if(!rrc) roomsFree(&RR);else free(rp);free(gb);
  W.homer.state=HS_IN_CAR;
  if(!strcmp(plant,"coin")&&W.coins.nworld) W.coins.c[0].x=W.coins.c[0].ox+=10000;
  if(!strcmp(plant,"wrench")&&bwCol()->nwrench) ((ColWrench *)bwCol()->wrench)[0].p[0]+=20;
  int ncoin=0,nwr=0;
  for(int k=0;k<nex;k++) { Exp *e=&ex[k];
    if(!strcmp(e->kind,"coin")) {
      ncoin++; int found=0;for(unsigned i=0;i<W.coins.nworld;i++) found+=near3(W.coins.c[i].ox,W.coins.c[i].oy,W.coins.c[i].oz,e->x,e->y,e->z);
      check("coin.position",e->name,found==1,found,1);
      for(int t=0;t<60;t++) coinsUpdate(&W.coins,e->x,e->y,e->z,0,1.f/60);
    } else if(!strcmp(e->kind,"wrench")) {
      nwr++; int idx=-1;for(unsigned i=0;i<bwCol()->nwrench;i++) if(!strcmp(bwCol()->wrench[i].name,e->name)&&near3(bwCol()->wrench[i].p[0],bwCol()->wrench[i].p[1],bwCol()->wrench[i].p[2],e->x,e->y,e->z))idx=i;
      if(idx<0) {check("wrench.missing",e->name,0,0,1);continue;}
      const ColWrench *wr=&bwCol()->wrench[idx];
      check("wrench.position",e->name,near3(wr->p[0],wr->p[1],wr->p[2],e->x,e->y,e->z)&&fabsf(wr->r-e->r)<.002f,idx,idx);
      /* Overlapping wrench spheres are legal (e.g. L3 Z1W2). Isolate this
       * pickup through progress so a neighbouring one cannot satisfy its repair. */
      W.G.wrenchTaken=~(1u<<idx);
      W.car.x=e->x;W.car.y=e->y-.8f;W.car.z=e->z;W.car.damage=1;W.car.destroyed=1;
      int taken=gameWrenchStep(&W.G);
      check("wrench.repair",e->name,taken==1&&!W.car.destroyed&&W.car.damage==0&&(W.G.wrenchTaken>>idx&1),taken,1);
      check("wrench.once",e->name,gameWrenchStep(&W.G)==0,0,0);
      check("wrench.drawable",e->name,W.G.wrenchInst[idx]>=0&& !W.sp.run[W.G.wrenchInst[idx]].alive,W.G.wrenchInst[idx]>=0,1);
    }
  }
  check("coin.total","disc",ncoin==(int)W.coins.nworld&&W.coins.collected==ncoin,W.coins.collected,ncoin);
  check("wrench.total","disc",nwr==(int)bwCol()->nwrench&&W.G.wrenches==(unsigned)nwr,W.G.wrenches,nwr);
  printf("RESULT L%d %s %d/%d cards=%d wasps=%d gags=%d coin_gags=%d coins=%d wrenches=%d\n",level,fail?"FAIL":"PASS",checks-fail,checks,nc,nw,ng,ncg,ncoin,nwr);
  return fail?1:0;
}
