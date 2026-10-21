// Силуэты за дальностью (слово Роба 16.10: «дальше прорисовка: 200 м и хотя бы силуэты, чтобы не было пустоты»). Файл silh.shr уровня (tools/silh_export.py, SIL1):
// блоки 100 м из ящиков (дома и холмы упрощены до коробок 25 м) и земли квадратами 50 м, без текстур, цвет = средний цвет текстуры × свет, низ ящика темнее.
// Рисуются блоки, у которых есть часть дальше дальности города (drawDist − 20 м), до SIL_FAR = 470 м, с глубиной, в осях камеры (как подложка клеток), туман к цвету горизонта
// (fogCol) от drawDist до SIL_FAR: чем дальше, тем темнее/гуще. Выключено по умолчанию: «flag silh 1/0» в сценарии или файл silh рядом с EBOOT (A/B в туре). Файл читается один раз при
// первом включении (на уровень), ≤ ~300 КБ, живёт в куче до смены уровня. Цена: до ~30 вызовов GE за кадр, не рисуется при нехватке бюджета списка (geOver).
// SILH_OLD=1 — функция не рисует вовсе (прежнее)
#pragma once
#ifndef SILH_OLD
#define SILH_OLD 0
#endif
#define SIL_FAR 470.f
typedef struct { float cx, cz, y0, y1, half, pad; unsigned voff, nv, ioff, ni, p1, p2; } SilBlk;
static int silhOn;
static unsigned char *silData; static unsigned silN, silSize; static int silLevel = -99; static const SilBlk *silB;
static unsigned silBlocks, silTris, silCalls;   // последний кадр: блоков, треугольников, вызовов
static void silhFree(void) { free(silData); silData = 0; silN = 0; silB = 0; silLevel = -99; }
static void silhLoad(int level) {
  silhFree(); silLevel = level;   // одна попытка на уровень: нет файла — молча без силуэтов
  char fn[256]; levelFile(fn, "silh.shr");
  SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f < 0) return;
  int sz = (int)sceIoLseek(f, 0, PSP_SEEK_END); sceIoLseek(f, 0, PSP_SEEK_SET);
  if (sz < 32 || sz > (2 << 20)) { sceIoClose(f); return; }
  unsigned char *m = (unsigned char *)memalign(64, (size_t)sz);
  if (!m || sceIoRead(f, m, (SceSize)sz) != sz || memcmp(m, "SIL1", 4)) { sceIoClose(f); free(m); return; }
  sceIoClose(f);
  unsigned n = *(unsigned *)(m + 4);
  if (32 + 48ull * n > (unsigned)sz) { free(m); return; }
  sceKernelDcacheWritebackRange(m, (unsigned)sz);
  silData = m; silSize = (unsigned)sz; silN = n; silB = (const SilBlk *)(m + 32);
  if (smkOn) { char s[96]; snprintf(s, sizeof s, "SILH loaded level=%d blocks=%u bytes=%u\n", level, n, (unsigned)sz); smkWrite(s); }
}
static void silhDraw(float ex, float ey, float ez) {
  silBlocks = silTris = silCalls = 0;
  if (SILH_OLD || !silhOn || inRoom() || clearChk) return;
  if (silLevel != gameLevel) silhLoad(gameLevel);
  if (!silN || geOver(GE_SOFT)) return;
  float near_ = drawDist - 20.f; if (near_ < 100.f) near_ = 100.f;
  ScePspFMatrix4 m; memset(&m, 0, sizeof m); m.x.x = m.y.y = m.z.z = m.w.w = 1.f;
  int started = 0;
  for (unsigned i = 0; i < silN; i++) {
    const SilBlk *b = &silB[i];
    float dx = b->cx - ex, dz = b->cz - ez, d = sqrtf(dx * dx + dz * dz), r = b->half * 1.42f;
    if (d + r < near_ || d - r > SIL_FAR) continue;
    float bb[6] = {b->cx - b->half, b->y0, b->cz - b->half, b->cx + b->half, b->y1, b->cz + b->half};
    if (!visBox(bb, 0, 0, 0)) continue;
    if (!started) {
      started = 1;
      sceGuDisable(GU_TEXTURE_2D); sceGuDisable(GU_BLEND); sceGuDisable(GU_ALPHA_TEST); sceGuDisable(GU_CULL_FACE);
      sceGuEnable(GU_DEPTH_TEST); sceGuDepthMask(GU_FALSE);
      sceGuEnable(GU_FOG); sceGuFog(near_, SIL_FAR, fogCol);
    }
    m.w.x = b->cx - ex; m.w.y = -ey; m.w.z = b->cz - ez;   // вершины: x, z от центра блока, y мировая; вид без переноса (как подложка клеток)
    sceGuSetMatrix(GU_MODEL, &m);
    sceGuDrawArray(GU_TRIANGLES, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_INDEX_16BIT | GU_TRANSFORM_3D, b->ni, silData + b->ioff, silData + b->voff);
    silBlocks++; silTris += b->ni / 3; silCalls++;
  }
  if (started) resetState();
}
