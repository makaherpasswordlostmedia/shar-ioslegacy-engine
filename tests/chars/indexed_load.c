#include "skin.h"
#include <stdio.h>
int main(int argc,char **argv){
  if(argc!=2)return 2;
  SkinModel *m=skinLoad(argv[1]);if(!m){puts("REJECT");return 1;}
  printf("LOAD %u bytes %u batches\n",m->h->size,m->h->nBatches);
  for(unsigned i=0;i<m->h->nBatches;i++){
    const SkinBatch *b=&m->b[i];unsigned n=skinBatchStoredVerts(b);
    if(n!=((b->flags&4)?b->pad[1]:b->nverts)){skinFree(m);return 3;}
  }
  skinFree(m);return 0;
}
