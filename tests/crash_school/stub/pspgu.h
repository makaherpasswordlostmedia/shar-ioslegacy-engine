// Заглушка pspgu для гейта tests/crash_school/ge_host.sh: каждая команда — слово (4 Б) в счётчике списка GE (ge_host.c),
// сколько слов пишет настоящий pspgu на вызов (sceGuSetMatrix/BoneMatrix — 13, sceGuTexImage — 4, sceGuDrawArray — 4…)
#ifndef STUB_PSPGU_H
#define STUB_PSPGU_H
#include "psptypes.h"
enum { GU_ALPHA_TEST = 0, GU_DEPTH_TEST, GU_SCISSOR_TEST, GU_STENCIL_TEST, GU_BLEND, GU_CULL_FACE, GU_DITHER, GU_FOG, GU_CLIP_PLANES,
       GU_TEXTURE_2D, GU_LIGHTING, GU_LIGHT0, GU_LIGHT1, GU_LIGHT2, GU_LIGHT3 };
#define GU_FALSE 0
#define GU_TRUE 1
#define GU_PROJECTION 0
#define GU_VIEW 1
#define GU_MODEL 2
#define GU_TEXTURE 3
#define GU_POINTS 0
#define GU_LINES 1
#define GU_LINE_STRIP 2
#define GU_TRIANGLES 3
#define GU_TRIANGLE_STRIP 4
#define GU_TRIANGLE_FAN 5
#define GU_SPRITES 6
#define GU_TEXTURE_32BITF (3 << 0)
#define GU_COLOR_8888 (7 << 2)
#define GU_VERTEX_32BITF (3 << 7)
#define GU_TRANSFORM_3D (0 << 23)
#define GU_PSM_8888 3
#define GU_PSM_T8 5
#define GU_TFX_MODULATE 0
#define GU_TCC_RGBA 1
#define GU_LINEAR 1
#define GU_REPEAT 0
#define GU_CLAMP 1
#define GU_GREATER 4
#define GU_ADD 0
#define GU_REVERSE_SUBTRACT 2
#define GU_SRC_ALPHA 2
#define GU_ONE_MINUS_SRC_ALPHA 3
#define GU_FIX 10
#define GU_DIRECTIONAL 0
#define GU_AMBIENT 1
#define GU_DIFFUSE 2
void sceGuEnable(int state);
void sceGuDisable(int state);
void sceGuDepthOffset(unsigned offset);
void sceGuDepthMask(int mask);
void sceGuSetMatrix(int type, const ScePspFMatrix4 *m);
void sceGuBoneMatrix(unsigned int index, const ScePspFMatrix4 *m);
void sceGuTexFunc(int tfx, int tcc);
void sceGuTexFilter(int min, int mag);
void sceGuTexScale(float u, float v);
void sceGuTexOffset(float u, float v);
void sceGuTexWrap(int u, int v);
void sceGuTexMode(int tpsm, int maxmips, int a2, int swizzle);
void sceGuTexImage(int mipmap, int width, int height, int tbw, const void *tbp);
void sceGuClutMode(unsigned int cpsm, unsigned int shift, unsigned int mask, unsigned int a3);
void sceGuClutLoad(int num_blocks, const void *cbp);
void sceGuLight(int light, int type, int components, const ScePspFVector3 *position);
void sceGuLightColor(int light, int component, unsigned int color);
void sceGuAmbient(unsigned int color);
void sceGuAmbientColor(unsigned int color);
void sceGuModelColor(unsigned int emissive, unsigned int ambient, unsigned int diffuse, unsigned int specular);
void sceGuAlphaFunc(int a0, int a1, int a2);
void sceGuBlendFunc(int op, int src, int dest, unsigned int srcfix, unsigned int destfix);
void sceGuDrawArray(int prim, int vtype, int count, const void *indices, const void *vertices);
void *sceGuGetMemory(int size);
int sceGuCheckList(void);
#endif
