// Real collect/SPR1 lifecycle. OLD must fail these same billboard assertions.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "collect.h"
static int visible(Collect *c, int inst) {
  if (inst < 0 || !c->sp.run[inst].alive) return 0;
  const SpType *t = c->sp.type + c->sp.inst[inst].type;
  int n = 0;
  for (unsigned b = 0; b < t->nBill; b++) {
    float v[12]; uint32_t rgba, flags; int tex;
    n += spBillQuad(&c->sp, inst, b, 0, 2, 5, v, &rgba, &tex, &flags) && (rgba >> 24) && tex >= 0;
  }
  return n;
}
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f,0,SEEK_END); unsigned sz=ftell(f); rewind(f);
  void *b=aligned_alloc(16,(sz+15u)&~15u); fread(b,1,sz,f); fclose(f);
  Collect c; if (collectInit(&c,b,sz)) return 2;
  Homer h; memset(&h,0,sizeof h); h.state=HS_FOOT;
  CollPlayer p={0,0,0,1,-1,0};
  int idle=visible(&c,c.kickFx); collectFootKick(&c,&h);
  collectStep(&c,&p,&h,0,0,0,.1f); int kick=visible(&c,c.kickFx);
  for(int i=0;i<60;i++) collectStep(&c,&p,&h,0,0,0,1.f/60.f); int after=visible(&c,c.kickFx);
  // CE_WASP_ZAP starts this source actor; the existing hurt state holds it.
  int shock=0, gone=0;
  if(c.shockFx>=0) {
    h.state=HS_HURT; spEnter(&c.sp,c.shockFx,1); c.sp.run[c.shockFx].alive=1; c.st.shockOn=1;
    collectStep(&c,&p,&h,0,0,0,.01f); shock=visible(&c,c.shockFx);
    h.state=HS_FOOT; collectStep(&c,&p,&h,0,0,0,.01f); gone=visible(&c,c.shockFx);
  }
  int ok=!idle && kick==1 && !after && shock==2 && !gone;
  printf("%s idle=%d kick=%d after=%d shock=%d gone=%d\n",ok?"PASS":"FAIL",idle,kick,after,shock,gone);
  collectFree(&c); free(b); return !ok;
}
