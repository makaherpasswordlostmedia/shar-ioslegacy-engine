// №386/387: поля от видимого силуэта, прозрачный холст не считается
#ifndef SHAR_UI_EDGE_PADDING_H
#define SHAR_UI_EDGE_PADDING_H
#include <math.h>
static inline float uiEdgeMargin(float visibleLeft) { return fmaxf(2.f, visibleLeft); }
static inline float uiIconTopShift(int bx, int by, int bw, int bh, int iw, int ih, int left, int top) {
  if (iw <= 0 || ih <= 0) return 0.f;
  float s = fminf((float)bw / iw, (float)bh / ih);
  float visibleLeft = bx + (bw - iw * s) * .5f + left * s;
  float visibleTop = by + (bh - ih * s) * .5f + top * s;
  return uiEdgeMargin(visibleLeft) - visibleTop;
}
#endif
