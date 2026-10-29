#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bonus.h"

static int check(const BnsTrack *t, int human, int winner, int all) {
  BonusRace b; brInit(&b, t, 1, 0, 4, human);
  float pos[4][3];
  for (int i=0;i<4;i++) for(int j=0;j<3;j++) pos[i][j]=100000.f;
  brUpdate(&b,(const float (*)[3])pos,BR_COUNT_S+.1f);
  for(int k=1;k<=b.ncp;k++) {
    const float *cp=b.t.cp[b.order[k%b.ncp]].c;
    memcpy(pos[winner],cp,3*sizeof(float));
    if(all) for(int i=0;i<4;i++) memcpy(pos[i],cp,3*sizeof(float));
    brUpdate(&b,(const float (*)[3])pos,.02f);
  }
  if(!b.r[winner].finished) return 1;
  if(all) return b.state!=BR_DONE;
  /* Published PS2 evidence: 20 seconds from FIRST winner, even if player has
     not finished. Exercise actual checkpoint traversal, not forged finished flags. */
  const float elapsed=b.sinceFirst;
  brUpdate(&b,(const float (*)[3])pos,19.9f-elapsed);
  if(b.state==BR_DONE) { fprintf(stderr,"closed before 20s human=%d winner=%d\n",human,winner); return 1; }
  brUpdate(&b,(const float (*)[3])pos,.2f);
  int fail=b.state!=BR_DONE;
  for(int i=0;i<4;i++) fail|=i==winner ? b.r[i].dnf!=0 : b.r[i].dnf!=1;
  if(fail) fprintf(stderr,"DNF failed human=%d winner=%d state=%d sinceFirst=%.2f\n",human,winner,b.state,b.sinceFirst);
  return fail;
}
int main(int argc,char **argv) {
  if(argc!=2) return 2;
  FILE *f=fopen(argv[1],"rb"); if(!f) return 2;
  fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
  void *data=malloc((size_t)n); if(!data || fread(data,1,(size_t)n,f)!=(size_t)n) return 2;fclose(f);
  BnsTrack t;if(bnsParse(&t,data,(unsigned)n)) return 2;
  int bad=0;
  bad+=check(&t,0,0,0);   /* human wins */
  for(int i=1;i<4;i++) bad+=check(&t,0,i,0); /* each opponent wins */
  bad+=check(&t,-1,2,0); /* all-CPU polygon has same result rule */
  bad+=check(&t,0,1,1); /* all finished closes immediately */
  free(data);printf("BONUS DNF/result: %s six first-winner cases\n",bad?"FAIL":"PASS");return !!bad;
}
