// Правка 313: заглушка pspgu.h для сборки viewer/fx.c на Маке (tests/me/fx_test.py): команды GE записываются, вершины — в отпечаток
#ifndef FXHOST_PSPGU_H
#define FXHOST_PSPGU_H
typedef struct { float x, y, z, w; } ScePspFVector4;
typedef struct { ScePspFVector4 x, y, z, w; } ScePspFMatrix4;
enum { GU_FOG = 1, GU_ALPHA_TEST, GU_TEXTURE_2D, GU_BLEND, GU_TFX_MODULATE = 0, GU_TCC_RGBA = 1, GU_LINEAR = 1, GU_CLAMP = 1, GU_REPEAT = 0,
       GU_TRUE = 1, GU_FALSE = 0, GU_MODEL = 3, GU_ADD = 0, GU_REVERSE_SUBTRACT = 2, GU_FIX = 10, GU_SRC_ALPHA = 2, GU_ONE_MINUS_SRC_ALPHA = 3,
       GU_PSM_8888 = 3, GU_PSM_T4 = 4, GU_PSM_T8 = 5, GU_TRIANGLES = 3, GU_GREATER = 6 };   // GU_GREATER: №731 вырезка по альфе (viewer/fx.c)
#define GU_INDEX_16BIT (2 << 11)
#define GU_TEXTURE_32BITF (3 << 0)
#define GU_COLOR_8888 (7 << 2)
#define GU_VERTEX_32BITF (3 << 7)
#define GU_TRANSFORM_3D 0
void sceGuDisable(int s); void sceGuEnable(int s);
void sceGuTexFunc(int a, int b); void sceGuTexFilter(int a, int b); void sceGuTexWrap(int a, int b);
void sceGuTexScale(float u, float v); void sceGuTexOffset(float u, float v); void sceGuDepthMask(int m);
void sceGuSetMatrix(int t, const ScePspFMatrix4 *m);
void sceGuBlendFunc(int op, int src, int dst, unsigned a, unsigned b);
void sceGuAlphaFunc(int func, int value, int mask);   // заглушка в fx_host.c: viewer/fx.c зовёт её у вырезки (№731)
void sceGuClutMode(unsigned cpsm, unsigned shift, unsigned mask, unsigned a3); void sceGuClutLoad(int n, const void *p);
void sceGuTexMode(int tpsm, int maxmips, int a2, int swizzle); void sceGuTexImage(int mip, int w, int h, int tbw, const void *p);
void sceGuTexFlush(void); void *sceGuGetMemory(int size);
void sceGuDrawArray(int prim, int vtype, int count, const void *indices, const void *vertices);
#endif
