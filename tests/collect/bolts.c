#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "collect.h"
static Collect c;
static unsigned char *blob;
static int idx;
static CollPlayer p;
static int begin(const char *path) {
  FILE *f=fopen(path,"rb");if(!f)return 0;fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);
  blob=aligned_alloc(16,(n+15u)&~15u);fread(blob,1,n,f);fclose(f);
  if(collectInit(&c,blob,n))return 0;
  for(unsigned i=0;i<c.nwasp;i++)if(!strcmp(c.wasp[i].name,"w_bonuscar"))idx=i;
  p=(CollPlayer){c.wasp[idx].x,c.wasp[idx].y,c.wasp[idx].z+6,1,-1,0};
  for(int f=0;f<1200;f++) {
    collectStep(&c,&p,0,0,0,0,1.f/120.f);
    CollEvent e;while(collectPop(&c,&e))if(e.type==CE_WASP_FIRE && e.idx==idx)return 1;
  }
  return 0;
}
static void end(void){collectFree(&c);free(blob);}
int main(int argc,char **argv) {
  if(argc!=2||!begin(argv[1]))return 2;
  int fail=0, delayed=!c.st.zaps && c.st.boltFired==1;
  printf("%s delayed: fired=%u zaps=%u\n",delayed?"PASS":"FAIL",c.st.boltFired,c.st.zaps);fail+=!delayed;
  int k=-1;for(unsigned i=0;i<c.nbolt;i++)if(c.st.boltOn[i]==1)k=i;
  if(k>=0) {
    float v=0;for(int j=0;j<3;j++)v+=c.st.boltV[k][j]*c.st.boltV[k][j];v=sqrtf(v);
    int speed=fabsf(v-c.wasp[idx].boltSpeed)<1e-4f;printf("%s speed %.3f source %.3f\n",speed?"PASS":"FAIL",v,c.wasp[idx].boltSpeed);fail+=!speed;
    const SpType *t=c.sp.type+c.sp.inst[c.bolt0+k].type;
    int shape=t->nBill==2 && t->nCol && c.sp.col[t->firstCol].kind==1;
    printf("%s source two billboards and sphere radius %.9f\n",shape?"PASS":"FAIL",t->nCol?c.sp.col[t->firstCol].h[0]:0);fail+=!shape;
  }
  for(int f=0;f<60&&!c.st.zaps;f++)collectStep(&c,&p,0,0,0,0,1.f/120.f);
  printf("%s stationary hit: zaps=%u\n",c.st.zaps?"PASS":"FAIL",c.st.zaps);fail+=!c.st.zaps;end();
  if(!begin(argv[1]))return 2;
  // Real movement after firing: 8 m/s (HOMER_RUN), perpendicular to aimed ray.
  for(int f=0;f<60;f++){p.x+=HOMER_RUN/120.f;collectStep(&c,&p,0,0,0,0,1.f/120.f);}
  int dodge=!c.st.zaps;printf("%s moving dodge: zaps=%u\n",dodge?"PASS":"FAIL",c.st.zaps);fail+=!dodge;end();
  printf("RESULT %s\n",fail?"FAIL":"PASS");return !!fail;
}
