#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bootseq.h"
int main(void) {
  int cases=0;
  for(int len=0;len<24;len++) {
    unsigned char *b=calloc(len?len:1,1); BootMarks out;
    if(len>=16) {
      memcpy(b,"BMK3",4);b[4]=1;b[6]=BMK_SLOT_W;b[8]=BMK_SLOT_H;b[10]=1;
      unsigned crc=bmkCrc32(b,len-4);
      for(int k=0;k<4;k++)b[len-4+k]=(unsigned char)(crc>>(8*k));
    }
    if(bootMarksParse(b,len,&out)!=-1) {printf("FAIL accepted short BMK3 len=%d\n",len);return 1;}
    free(b);cases++;
  }
  printf("PASS short BMK3 rejected safely: %d lengths\n",cases);return 0;
}
