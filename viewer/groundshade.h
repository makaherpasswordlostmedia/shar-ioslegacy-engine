#ifndef SHAR_GROUNDSHADE_H
#define SHAR_GROUNDSHADE_H
#ifdef SKIN_HOST
// Host wheel tests exercise model matrices; GU rendering is stubbed there
static inline unsigned groundShadeAlpha(float alpha) { return (unsigned)(alpha<0.f?0.f:alpha>255.f?255.f:alpha); }
static inline void groundShadeBegin(void) {}
static inline void groundShadeEnd(void) {}
#else
extern int groundShadeOld;
void groundShadeView(const float *eye, const float *forward, const float *right, const float *up, float focal);
unsigned groundShadeAlpha(float alpha);
void groundShadeBegin(void);
void groundShadeEnd(void);
#endif
#endif
