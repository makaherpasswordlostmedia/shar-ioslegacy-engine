#include <stdio.h>
#include <string.h>
#include "pcm_output.h"
#include "../viewer/mebudget.h"
// Actual async-consumer contract: blocking waits for the PREVIOUS queued pointer,
// then queues the new one and returns while it is still being read
static PcmOutput pool;static const short *pending;static short expected[1024];
int main(int argc,char **argv){
  (void)argc;(void)argv;int changed=0,frames=0;
  for(int n=0;n<1000;n++){
    short *p=pcmOutputBuffer(&pool);
    for(int i=0;i<1024;i++)p[i]=(short)(n*17+i*3);
    // Deferred consumer reads old samples when outputBlocking waits
    if(pending&&memcmp(pending,expected,sizeof expected))changed++;
    pending=p;memcpy(expected,p,sizeof expected);pcmOutputQueued(&pool);frames++;
  }
  int bad=!meFxWithinBudget(128,0,0)||!meFxWithinBudget(32,32,64)||meFxWithinBudget(129,0,0)||meFxWithinBudget(128,1,0)||meFxWithinBudget(400,0,0)||meFxWithinBudget(-1,0,0);
  printf("%s PCM frames=%d overwritten-queued=%d buffers=%d FX-budget=%s\n",changed||bad?"FAIL":"PASS",frames,changed,PCM_OUTPUT_BUFFERS,bad?"FAIL":"PASS");
  return changed||bad?1:0;
}
