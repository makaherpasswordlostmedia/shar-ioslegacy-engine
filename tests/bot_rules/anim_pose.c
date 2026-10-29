/* Actual ANM1/COL/SPR: at every live volume in four clip phases, aoStep
   must produce the same position as explicit placement of the rendered pose.
   OLD retains the first-instance distance cull and must fail on real levels. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "props.h"
#include "stateprops.h"
#include "animobj.h"

static int nok, nfail;
static void check(const char *name, int ok, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
#include <stdarg.h>
static void check(const char *name, int ok, const char *fmt, ...) {
  char b[256]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof b, fmt, a); va_end(a);
  printf("CHECK %-30s %s %s\n", name, ok ? "ok  " : "FAIL", b); if (ok) nok++; else nfail++;
}
static void *readAll(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); long s = ftell(f); rewind(f);
  unsigned char *b = aligned_alloc(16, ((size_t)s + 15) & ~(size_t)15);
  if (!b || fread(b, 1, (size_t)s, f) != (size_t)s) { fclose(f); free(b); return 0; }
  fclose(f); *n = (size_t)s; return b;
}
static ColWorld W; static Props P; static StateProps S; static AnimObjs A;
static int plantNolive, plantNoact, plantFar;

static void step(float px, float py, float pz, int foot, int act, float dt) {
  spUpdate(&S, &W, NULL, NULL, dt);
  if (!plantNolive) aoStep(&A, &S, &W, px, py, pz, foot, plantNoact ? 0 : act, dt);
}
static const float *volC(unsigned v) { const AoVol *V = &A.vol[v]; return V->kind == 0 ? W.box[V->col].c : W.cyl[V->col].c; }
static int ground(float x, float z, float top, float *y) { return colGround(&W, x, z, top, -50.f, y, 0); }
// сетка знает объём v в каждой клетке его xz-габарита
static int gridKnows(unsigned v) {
  const AoVol *V = &A.vol[v]; float lo[2], hi[2];
  if (V->kind == 0) {
    const ColBox *B = &W.box[V->col]; float ex = 0, ez = 0;
    ex = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
    ez = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2];
    lo[0] = B->c[0] - ex; hi[0] = B->c[0] + ex; lo[1] = B->c[2] - ez; hi[1] = B->c[2] + ez;
  } else {
    const ColCyl *C = &W.cyl[V->col]; float cx = fabsf(C->axis[0]) * C->halfLen + C->r, cz = fabsf(C->axis[2]) * C->halfLen + C->r;
    lo[0] = C->c[0] - cx; hi[0] = C->c[0] + cx; lo[1] = C->c[2] - cz; hi[1] = C->c[2] + cz;
  }
  uint32_t want = ((V->kind == 0 ? 1u : 2u) << 29) | V->col;
  int gx0 = (int)floorf((lo[0] - W.ox) * W.inv), gx1 = (int)floorf((hi[0] - W.ox) * W.inv);
  int gz0 = (int)floorf((lo[1] - W.oz) * W.inv), gz1 = (int)floorf((hi[1] - W.oz) * W.inv);
  for (int gz = gz0; gz <= gz1; gz++) for (int gx = gx0; gx <= gx1; gx++) {
    if (gx < 0 || gz < 0 || gx >= W.W || gz >= W.H) return 0;
    uint32_t c = (uint32_t)gz * (uint32_t)W.W + (uint32_t)gx; int hit = 0;
    for (uint32_t k = W.cellStart[c]; k < W.cellStart[c + 1]; k++) if (W.refs[k] == want) { hit = 1; break; }
    if (!hit) return 0;
  }
  return 1;
}

int main(int argc,char**argv){
 if(argc!=2)return 2;
 size_t n;unsigned char*lv=readAll(argv[1],&n);unsigned co=*(unsigned*)(lv+92),po=*(unsigned*)(lv+96);unsigned ps=*(unsigned*)(lv+po+40);
 if(colInit(&W,lv+co,po-co)||propsInit(&P,lv+po,ps)||spInit(&S,P.spr,P.sprSize)||aoInit(&A,lv+po,ps,&S,&W))return 2;
 unsigned checks=0,bad=0;float maxerr=0;
 for(unsigned k=0;k<A.nobj;k++){
 const AoObj*o=&A.obj[k];if(!o->nInst||!o->nVol||o->nfr<2)continue;
 for(int ph=1;ph<=4;ph++){
  float frame=(o->nfr-1)*ph/5.f;
  for(unsigned i=o->firstInst;i<o->firstInst+o->nInst;i++){S.run[i].poseF=frame;S.run[i].poseValid=0;}aoPlace(&A,&S,&W,k);
  float target[1024][3];if(o->nVol>1024)return 3;
  for(unsigned v=0;v<o->nVol;v++)memcpy(target[v],volC(o->firstVol+v),12);
  for(unsigned v=0;v<o->nVol;v++){
   for(unsigned i=o->firstInst;i<o->firstInst+o->nInst;i++){S.run[i].poseF=0;S.run[i].poseValid=0;}aoPlace(&A,&S,&W,k);
   for(unsigned i=o->firstInst;i<o->firstInst+o->nInst;i++){S.run[i].poseF=frame;S.run[i].poseValid=0;}A.run[k].f=frame;A.run[k].playing=1;
   aoStep(&A,&S,&W,target[v][0],target[v][1],target[v][2],0,0,0);
   const float*c=volC(o->firstVol+v);float e=sqrtf(powf(c[0]-target[v][0],2)+powf(c[1]-target[v][1],2)+powf(c[2]-target[v][2],2));checks++;if(e>maxerr)maxerr=e;
   if(e>.02f){bad++;printf("BAD actor %u vol %u phase %.2f dist %.2f error %.3f xyz %.3f %.3f %.3f\n",k,v,frame,hypotf(target[v][0]-S.run[o->firstInst].x,target[v][2]-S.run[o->firstInst].z),e,target[v][0],target[v][1],target[v][2]);}
  }
 }
 }
 printf("CHECKS %u BAD %u MAX %.4f\n",checks,bad,maxerr);return bad?1:0;
}
