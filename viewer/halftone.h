// Полутон (слово Роба 17.10, видео IMG_7280): тени, свет, огонь — точками, а не полупрозрачностью. Узор 32×32 текселя (4×4 точки по 8×8),
// альфа узора: 255 в центре точки, 0 в углу клетки; альфа вершины × альфа узора против порога альфа-теста = размер точки, поэтому градиент
// альфы по вершинам даёт редеющие к краю точки. Без смешивания и сортировки, запись глубины выключена. Сетка повёрнута на 45° — ромбиком,
// как печатный полутон. Подключается из main.c после main_render.h (resetState), до lightsprite.h и spritelight.h.
#ifndef HALFTONE_H
#define HALFTONE_H
#define HT_N 32
static unsigned htTex[HT_N * HT_N] __attribute__((aligned(16))); static int htReady;
static void htInit(void) {
  for (int y = 0; y < HT_N; y++) for (int x = 0; x < HT_N; x++) {
    float cx = (x & 7) - 3.5f, cy = (y & 7) - 3.5f, d = sqrtf(cx * cx + cy * cy) / 4.95f;   // 0 в центре точки, 1 в углу клетки
    float a = 255.f * (1.f - d); if (a < 1.f) a = 1.f;
    htTex[y * HT_N + x] = ((unsigned)a << 24) | 0x00FFFFFFu; }
  sceKernelDcacheWritebackRange(htTex, sizeof htTex); htReady = 1;
}
// координаты на плоскости (м) -> UV узора: сетка под 45° с шагом cell
static inline void htUV(float lx, float lz, float cell, float *u, float *v) {
  float ru = (lx + lz) * .70710678f, rv = (lz - lx) * .70710678f; *u = ru / (4.f * cell); *v = rv / (4.f * cell);
}
static void htBegin(int ref) {   // ref — порог альфа-теста (меньше — крупнее точки)
  if (!htReady) htInit();
  ScePspFMatrix4 I; memset(&I, 0, sizeof I); I.x.x = I.y.y = I.z.z = I.w.w = 1.f; sceGuSetMatrix(GU_MODEL, &I);
  sceGuEnable(GU_TEXTURE_2D); sceGuTexMode(GU_PSM_8888, 0, 0, 0); sceGuTexImage(0, HT_N, HT_N, HT_N, htTex);
  sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuTexFilter(GU_NEAREST, GU_NEAREST); sceGuTexWrap(GU_REPEAT, GU_REPEAT);
  sceGuTexMapMode(GU_TEXTURE_COORDS, 0, 0); sceGuTexScale(1.f, 1.f); sceGuTexOffset(0.f, 0.f); sceGuTexFlush();
  sceGuDisable(GU_BLEND); sceGuEnable(GU_ALPHA_TEST); sceGuAlphaFunc(GU_GREATER, ref, 0xff);
  sceGuDepthMask(GU_TRUE); sceGuDepthOffset(0); sceGuDisable(GU_CULL_FACE);
}
static void htEnd(void) { sceGuDisable(GU_ALPHA_TEST); sceGuDepthMask(GU_FALSE); sceGuDisable(GU_TEXTURE_2D); sceGuTexScale(128.f, 128.f); resetState(); }
#endif
