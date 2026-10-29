// Deterministic fixtures shared with host checks; native game DSP, no PSP APIs
#pragma once
#include <string.h>
#include "../viewer/spatialdsp.h"
#include "../viewer/fxdsp.h"
static void spatialInput(SpatialJob *j,int n,unsigned seed) {
  memset(j,0,sizeof *j); j->count=n;j->right[0]=32768;
  for(int i=0;i<n;i++) {
    MixPoint *p=&j->point[i];p->on=1;p->min=64;p->max=960;
    seed=seed*1664525u+1013904223u;p->p[0]=(int)(seed%2201)-1100;
    seed=seed*1664525u+1013904223u;p->p[2]=(int)(seed%1801)-900;
    p->p[1]=i%31;j->gain[i][0]=j->gain[i][1]=32768;
  }
}
static void mixerInput(MixJob *j,const unsigned char *bank,unsigned samples,unsigned start,unsigned end,
                       unsigned rate,int ch,const short hist[4],int n,unsigned seed) {
  memset(j,0,sizeof *j);j->data=bank;j->right[0]=32768;
  for(int i=0;i<n;i++) {
    MixVoice *v=&j->v[i];v->on=1;v->ch=ch;v->stream=-1;v->loop=1;v->rate=rate;
    v->tgl=v->tgr=8192/(n?n:1);v->step=v->tstep=(unsigned)((unsigned long long)rate*65536/44100);
    v->end=samples;v->loopStart=start;v->loopEnd=end;memcpy(v->lhist,hist,sizeof v->lhist);
    v->point.on=1;v->point.min=64;v->point.max=960;v->spatialStart=1;
    v->point.p[0]=(int)((seed+i*71)%641)-320;v->point.p[2]=(int)((seed*7+i*53)%701);
  }
}
static void particlesInput(FxJob *j,FxEmit *e,FxV *out,int n,unsigned seed,unsigned fcsr) {
  memset(j,0,sizeof *j);memset(e,0,sizeof *e);
  e->aspect=1;e->cols=e->rows=e->nFr=1;e->blend=1;e->angleMode=2;
  for(int i=0;i<NOL;i++){e->ol[i]=0xc0ffffffu;e->olSize[i]=1.f-.5f*i/(NOL-1);e->olSpeed[i]=1;e->olSpin[i]=1;e->olWeight[i]=1;}
  j->E=e;j->vout=out;j->np=n;j->nt=1;j->stage=FXD_SIM|FXD_BUILD;j->fcsr=fcsr;j->dt=1.f/60;j->fz=1;j->fillK=1;
  j->inv[0][0]=(unsigned)(unsigned long)e;j->inv[0][1]=sizeof *e;
  for(int i=0;i<n;i++){
    FxPart *p=&j->ps[i];p->x=(i%13-6)*.4f;p->y=(i%7)*.3f;p->z=3.f+(i%41);
    p->vx=.25f*(int)(seed%5);p->vy=1;p->vz=.5f;p->ga=-9.8f;
    p->age=(i%19)*.045f;p->inv=1;p->size=1;p->spin=.25f;p->lnd=-.5f;
    p->rgb=0x00ffffffu;p->ak=1;p->inst=i%FX_MAX_INST;
  }
}
