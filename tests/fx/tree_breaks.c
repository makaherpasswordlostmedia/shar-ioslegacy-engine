// Actual SPR1 in the exported L6: native tree/pole clips must start, move and return to the hidden pool
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
int main(int argc,char **argv) {
  if(argc!=2)return 2;
  FILE *f=fopen(argv[1],"rb"); if(!f)return 2;
  fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(!b || fread(b,1,n,f)!=(size_t)n)return 2;fclose(f);
  unsigned po;memcpy(&po,b+96,4);Props p;StateProps s;
  if(propsInit(&p,b+po,*(unsigned *)(b+po+40)) || spInit(&s,p.spr,p.sprSize))return 2;
  int wanted[]={23,25,27,28},fail=0;
  for(unsigned q=0;q<sizeof wanted/sizeof *wanted;q++) {
    int ti=-1,pi=-1,slot=-1;
    for(unsigned t=0;t<s.ntype;t++)if(s.type[t].kind==1 && s.type[t].bindex==wanted[q])ti=t;
    if(ti<0){printf("FAIL missing native break%d\n",wanted[q]);fail++;continue;}
    for(unsigned t=0;t<p.ntype;t++)if(spBreakOf(&s,t)==ti)pi=t;
    if(pi<0 || !s.type[ti].nPiece || s.type[ti].life<=0){printf("FAIL unbound/empty break%d\n",wanted[q]);fail++;continue;}
    float pos[]={0,0,0},quat[]={1,0,0,0};
    if(!spBreak(&s,ti,pos,quat)){printf("FAIL fallback whole prop break%d\n",wanted[q]);fail++;continue;}
    for(unsigned i=0;i<s.ninst;i++)if(s.inst[i].type==(unsigned)ti && s.run[i].state==1)slot=i;
    if(slot<0){fail++;continue;}
    spPose(&s,slot);float before[16],after[16];unsigned k=0; // spPieceMatrix takes a local piece index
    spPieceMatrix(&s,slot,k,before);
    float duration=fminf(.3f,s.type[ti].life*.4f);
    for(float tm=0;tm<duration;tm+=.02f)spUpdate(&s,0,0,0,.02f);
    spPose(&s,slot);spPieceMatrix(&s,slot,k,after);
    float delta=0;for(int a=0;a<16;a++)delta+=fabsf(before[a]-after[a]);
    if(delta<1e-4f){printf("FAIL stationary chunk break%d\n",wanted[q]);fail++;}
    for(float tm=0;tm<s.type[ti].life+.2f;tm+=.05f)spUpdate(&s,0,0,0,.05f);
    if(s.run[slot].state!=0 || spDrawable(&s,slot,0,0,100.f)){printf("FAIL stuck clip break%d\n",wanted[q]);fail++;}
    printf("break%d mapped PRP%d pieces%d motion%.4f state%d\n",wanted[q],pi,s.type[ti].nPiece,delta,s.run[slot].state);
  }
  printf("%s failures%d\n",fail?"FAIL":"PASS",fail);spFree(&s);propsFree(&p);free(b);return fail?1:0;
}
