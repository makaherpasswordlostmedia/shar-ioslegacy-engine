#ifndef SHAR_SPATIALDSP_H
#define SHAR_SPATIALDSP_H
#include "mixdsp.h"
#define SPATIAL_MAX_POINTS 128
typedef struct SpatialJob {
  int listener[3], right[2], count, pad[10];
  MixPoint point[SPATIAL_MAX_POINTS];
  int gain[SPATIAL_MAX_POINTS][2];
} __attribute__((aligned(64))) SpatialJob;
// The full mixer's attenuation/pan, without audio decoding
static void mixSpatialBatchRun(SpatialJob *j) {
  int n=j->count;if(n<0)n=0;if(n>SPATIAL_MAX_POINTS)n=SPATIAL_MAX_POINTS;
  for(int i=0;i<n;i++)mixPointGains(j->listener,j->right,&j->point[i],&j->gain[i][0],&j->gain[i][1]);
}
#endif
