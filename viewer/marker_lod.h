#ifndef SHAR_MARKER_LOD_H
#define SHAR_MARKER_LOD_H
#include <math.h>
typedef struct { float eye[3], forward[3], right[3], up[3], focal; } MarkerView;
#define MARKER_SMALL_PX 14.f
#define MARKER_ICON_PX 16.f
// Project the loaded marker's bounds, not a fixed world-distance threshold
static inline float markerPixels(const MarkerView *v, const float *p, const float *h, float *depth) {
  float z=0, x=0, y=0;
  for(int k=0;k<3;k++) { z+=(p[k]-v->eye[k])*v->forward[k]; x+=fabsf(v->right[k])*h[k]; y+=fabsf(v->up[k])*h[k]; }
  *depth=z;
  return z>.1f && v->focal>0.f ? 2.f*fmaxf(x,y)*v->focal/z : -1.f;
}
static inline int markerIsSmall(float pixels) { return pixels>0.f && pixels<MARKER_SMALL_PX; }
#endif
