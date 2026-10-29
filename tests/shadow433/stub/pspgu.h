// CPU capture of actual carVisDrawShadow GE state and vertices
#pragma once
#define GU_PI 3.14159265358979f
enum { GU_ADD, GU_ALPHA_TEST, GU_BLEND, GU_COLOR_8888, GU_FALSE, GU_FIX, GU_FOG, GU_INDEX_16BIT, GU_MODEL, GU_ONE_MINUS_SRC_ALPHA,
       GU_SRC_ALPHA, GU_TEXTURE_2D, GU_TEXTURE_32BITF, GU_TRANSFORM_3D, GU_TRIANGLES, GU_TRUE, GU_VERTEX_32BITF };
typedef struct { float x, y, z, w; } ScePspFVector4;
typedef struct { ScePspFVector4 x, y, z, w; } ScePspFMatrix4;
#define GU_DITHER 99
int sceGuGetStatus(int a);
void sceGuDepthOffset(int a);
static inline void sceGuBlendFunc(int a, int b, int c, unsigned d, unsigned e) { (void)a; (void)b; (void)c; (void)d; (void)e; }
static inline void sceGuDepthMask(int a) { (void)a; }
void sceGuDisable(int a);
void sceGuEnable(int a);
void sceGuDrawArray(int a, int b, int c, const void *d, const void *e);
static unsigned char guMem_[65536];
static inline void *sceGuGetMemory(int n) { (void)n; return guMem_; }
static inline void sceGuSetMatrix(int a, const void *m) { (void)a; (void)m; }
static inline void sceGuTexScale(float a, float b) { (void)a; (void)b; }
