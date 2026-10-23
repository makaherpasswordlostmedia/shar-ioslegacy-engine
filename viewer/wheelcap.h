// wheelcap.h — №867 (Роб 23.10: «на покрышках картинка диска: сверху блик, снизу тень; поедешь — блик и тень крутятся, будто крутится
// источник света; чёрная часть пусть крутится, а картинки-диски не должны»): колесо машины — один кусок (протектор + боковины с картинкой
// диска), движок крутил его целиком вокруг оси X модели. Правило: треугольники, смотрящие вдоль оси колеса (|n.x| >= 0,7·|n|, боковины), — без
// вращения (подвеска и руль остаются), остальные (протектор) крутятся. Данные не меняются: один раз на кусок треугольники переставляются
// в памяти «боковины → протектор» (устойчиво), кэш сбрасывается в память (GE читает из RAM), число боковых запоминается по адресу вершин.
// Клетка перезагрузилась (порядок прежний) — проверка первого и пограничного треугольника замечает и переставляет снова.
// Общий для своей машины (CAR1, main_loop.h), трафика и машин миссий (traffic.c trafficDrawModel). WHEELCAP867_OLD=1 — как было
#ifndef WHEELCAP_H
#define WHEELCAP_H
#ifdef SKIN_HOST   // Mac-гейты (tests/aicar, tests/traffic): кэша GE нет, memalign — malloc
static inline void sceKernelDcacheWritebackRange(const void *p_, unsigned n_) { (void)p_; (void)n_; }
#ifndef memalign
#define memalign(a_, n_) malloc(n_)
#endif
#else
#include <pspkernel.h>
#endif
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifndef WHEELCAP867_OLD
#define WHEELCAP867_OLD 0
#endif
#define WC_SLOTS 512
typedef struct { const void *v; int ni, capN; } WcEnt;
static WcEnt wcTab[WC_SLOTS];
static unsigned wcSplits;   // служебно: перестановок за прогон
static inline int wcIsCap(const unsigned char *t, int vs, int po) {
  const short *a = (const short *)(t + po), *b = (const short *)(t + vs + po), *c = (const short *)(t + 2 * vs + po);
  float ux = (float)b[0] - a[0], uy = (float)b[1] - a[1], uz = (float)b[2] - a[2], wx = (float)c[0] - a[0], wy = (float)c[1] - a[1], wz = (float)c[2] - a[2];
  float nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx, l2 = nx * nx + ny * ny + nz * nz;
  return l2 > 0.f && nx * nx >= .49f * l2;
}
// вершины куска без индексов (vs 12 или 16 Б, ni кратно 3) -> число вершин боковин в начале куска; 0 — делить нечего (рисовать целиком)
static int wheelCapN(void *vb, int ni, int vs) {
  if (WHEELCAP867_OLD || !vb || ni < 6 || ni % 3 || (vs != 12 && vs != 16)) return 0;
  int po = vs == 12 ? 6 : 8, nt = ni / 3; unsigned char *v = (unsigned char *)vb;
  unsigned h = (unsigned)(((uintptr_t)vb >> 4) * 2654435761u) % WC_SLOTS; WcEnt *e = 0;
  for (int k = 0; k < 8; k++) { WcEnt *q = &wcTab[(h + (unsigned)k) % WC_SLOTS]; if (q->v == vb && q->ni == ni) { e = q; break; } if (!q->v && !e) e = q; }
  if (e && e->v == vb && e->ni == ni) {   // проверка: порядок на месте (данные не перечитаны)
    int c = e->capN / 3;
    if (c <= 0 || ((wcIsCap(v, vs, po)) && (c >= nt || !wcIsCap(v + (size_t)c * 3 * vs, vs, po)))) return e->capN;
  }
  if (!e) e = &wcTab[h];   // занято — вытесняем
  int caps = 0; for (int t = 0; t < nt; t++) caps += wcIsCap(v + (size_t)t * 3 * vs, vs, po);
  if (caps > 0 && caps < nt) {
    unsigned char *tmp = (unsigned char *)malloc((size_t)ni * vs);
    if (!tmp) return 0;
    size_t o = 0, tb = (size_t)3 * vs;
    for (int pass = 1; pass >= 0; pass--) for (int t = 0; t < nt; t++) { const unsigned char *s = v + (size_t)t * tb; if (wcIsCap(s, vs, po) == pass) { memcpy(tmp + o, s, tb); o += tb; } }
    memcpy(v, tmp, (size_t)ni * vs); free(tmp);
    sceKernelDcacheWritebackRange(v, (unsigned)(ni * vs));   // GE читает вершины из памяти (урок №863)
    wcSplits++;
  }
  e->v = vb; e->ni = ni; e->capN = (caps > 0 && caps < nt) ? caps * 3 : 0;
  return e->capN;
}
#endif
