// Real Homer attack -> gameAfterCar -> gamePropKick -> native SPR1 clip.
// Inputs: exported level, Homer CHR1, required BreakablesEnum indices.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "game.h"
static int bad, checks, hits;
static void check(int yes,const char *label,int idx) {
  checks++; if(!yes){bad++;printf("FAIL break%d %s\n",idx,label);}
}
static void event(void *u,const HomerEvent *e) {(void)u;if(e->type==HOMER_EV_HIT)hits++;}
int main(int argc,char **argv) {
  if(argc<4)return 2;
  FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char *blob=malloc(n);
  if(!blob || fread(blob,1,n,f)!=(size_t)n)return 2;fclose(f);
  unsigned po,co;memcpy(&po,blob+96,4);memcpy(&co,blob+92,4);
  ColWorld world={0};if(colInit(&world,blob+co,n-co))return 2;
  SkinModel *model=skinLoad(argv[2]);if(!model)return 2;
  for(int a=3;a<argc;a++) {
    int idx=atoi(argv[a]), found=0;
    Props props={0};StateProps sp={0};unsigned psz;memcpy(&psz,blob+po+40,4);
    if(propsInit(&props,blob+po,psz) || spInit(&sp,props.spr,props.sprSize))return 2;
    for(unsigned i=0;i<props.ninst;i++) {
      int particle,bi;propsTypeFx(&props,props.def[i].type,&particle,&bi);
      if(bi!=idx)continue;
      found=1;
      int bt=spBreakOf(&sp,props.def[i].type);
      check(bt>=0,"native clip mapped",idx);
      if(bt<0)break;
      for(unsigned k=0;k<props.ninst;k++)props.st[k].hidden=k!=i;
      for(unsigned k=0;k<sp.ninst;k++)if(sp.type[sp.inst[k].type].kind!=1)sp.run[k].alive=0;
      Homer h={0};if(homerInit(&h,model))return 2;
      PropState *st=&props.st[i];
      float x=st->x,z=st->z-.85f;
      homerPlace(&h,&world,x,props.def[i].y+.5f,z,0);
      Car car={0};carInit(&car,NULL,&world,x+100,h.y,z+100,0);
      Coins coins={0};int yes=1,no=0,spInitState=0,destroyed=0;
      unsigned char states[512]={0};float heat=0,calm=0,lift=.62f;
      Game g={.pWorld=&world,.pCar=&car,.pProps=&props,.pSp=&sp,.pCoins=&coins,.pHomer=&h,
        .pHaveCol=&yes,.pHaveProps=&yes,.pHaveSP=&yes,.pHaveCoins=&no,.pHaveHomer=&yes,
        .pHnrHeat=&heat,.pHnrCalm=&calm,.pWasDestroyed=&destroyed,.pSpSt=states,.pSpStInit=&spInitState,
        .pLift=&lift,.hnrOff=1};g.hk.homerEvent=event;
      props.onKick=gamePropKick;props.kickUser=&g;
      hits=0;GamePad pad={0};
      // A real kick safely outside the whole bounding sphere must miss.
      float reach=sqrtf(st->hx*st->hx+st->hy*st->hy+st->hz*st->hz)+3.f;
      homerPlace(&h,&world,st->x+reach,props.def[i].y+.5f,z,0);
      for(int frame=0;frame<45;frame++) {
        pad.hit=frame==0?GP_SQUARE:0;gameAfterCar(&g,&pad,1.f/60);
      }
      check(hits==1,"one actual distant attack",idx);
      check(!st->hidden,"distant attack does not destroy prop",idx);
      int active=0;for(unsigned k=0;k<sp.ninst;k++)if(sp.inst[k].type==(unsigned)bt && sp.run[k].state==1)active++;
      check(!active,"distant attack does not start debris",idx);
      // Analytic controls on the exported, rotated box: inside and outside each face.
      float axes[16];propPieceMatrix(st,st->cx,st->cy,st->cz,1,axes);
      float half[3]={st->hx,st->hy,st->hz};
      for(int axis=0;axis<3;axis++)for(int side=-1;side<=1;side+=2) {
        float point[3],closest[3];
        for(int k=0;k<3;k++)point[k]=axes[12+k]+axes[4*axis+k]*side*(half[axis]+.5f);
        propsClosestPoint(&props,i,point,closest);
        float dist=0;for(int k=0;k<3;k++)dist+=(point[k]-closest[k])*(point[k]-closest[k]);
        check(fabsf(sqrtf(dist)-.5f)<.001f,"rotated box face distance",idx);
      }
      homerInit(&h,model);homerPlace(&h,&world,x,props.def[i].y+.5f,z,0);hits=0;
      printf("KICKPOS break%d xyz=%.6f,%.6f,%.6f heading=%.6f\n",idx,h.x,h.y,h.z,h.h);
      for(int frame=0;frame<45;frame++) {
        pad.hit=frame==0?GP_SQUARE:0;gameAfterCar(&g,&pad,1.f/60);
      }
      check(hits==1,"one actual Homer attack",idx);
      check(st->hidden && st->asleep,"whole prop hidden after kick",idx);
      int slot=-1;
      for(unsigned k=0;k<sp.ninst;k++)if(sp.inst[k].type==(unsigned)bt && sp.run[k].state==1)slot=k;
      check(slot>=0,"native debris playing",idx);
      if(slot>=0) {
        unsigned pieces=sp.type[bt].nPiece;
        float *before=calloc(pieces*16,sizeof(float)),after[16];
        spPose(&sp,slot);for(unsigned k=0;k<pieces;k++)spPieceMatrix(&sp,slot,k,before+k*16);
        for(int k=0;k<12;k++)gameAfterCar(&g,&pad,1.f/60);
        spPose(&sp,slot);float delta=0;
        for(unsigned piece=0;piece<pieces;piece++) {
          spPieceMatrix(&sp,slot,piece,after);
          for(int k=0;k<16;k++)delta+=fabsf(before[piece*16+k]-after[k]);
        }
        free(before);
        check(delta>1e-4f,"native debris moves",idx);
        for(float t=0;t<sp.type[bt].life+.2f;t+=1.f/60)gameAfterCar(&g,&pad,1.f/60);
        check(sp.run[slot].state==0 && !spDrawable(&sp,slot,0,0,1e6f),"debris returns to hidden pool",idx);
      }
      printf("break%d prop%u footY%.3f centreY%.3f radius%.3f height%.3f hidden%d hits%d\n",
        idx,i,h.y,st->y,props.types[props.def[i].type].radius,2*st->hy,st->hidden,hits);
      break;
    }
    check(found,"source family has exported prop instance",idx);
    spFree(&sp);propsFree(&props);
  }
  printf("%s checks%d failures%d\n",bad?"FAIL":"PASS",checks,bad);
  colFree(&world);free(blob);return bad?1:0;
}
