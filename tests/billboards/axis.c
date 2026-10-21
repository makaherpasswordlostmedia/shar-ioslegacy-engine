// Exercise the actual spBillQuad with native joint and instance matrices.
#include <string.h>
#include "stateprops.h"
int axisQuad(int mode, const float *joint, const float *world, const float *pos,
             const float *eye, float width, float height, float *out) {
  StateProps sp = {0}; SpType type = {.nBill=1, .nState=1};
  SpState state = {.vis=1}; SpInst inst = {0}; SpRun run = {.alive=1};
  SpBill bill = {.mode=mode,.w=width,.h=height,.rgba=0xffffffff};
  memcpy(bill.t,pos,12); memcpy(run.R,world,36); run.jm=(float*)joint;
  sp.type=&type;sp.state=&state;sp.inst=&inst;sp.run=&run;sp.bill=&bill;
  unsigned colour,flags;int tex;
  return spBillQuad(&sp,0,0,eye[0],eye[1],eye[2],out,&colour,&tex,&flags);
}
int axisModes(const void *data, unsigned size, unsigned *counts) {
  StateProps sp; int err=spInit(&sp,data,size); if(err)return err;
  memset(counts,0,4*sizeof(unsigned));
  for(unsigned t=0;t<sp.ntype;t++)for(unsigned b=0;b<sp.type[t].nBill;b++) {
    unsigned mode=sp.bill[sp.type[t].firstBill+b].mode;
    if(mode>3){spFree(&sp);return -99;} counts[mode]++;
  }
  spFree(&sp);return 0;
}
