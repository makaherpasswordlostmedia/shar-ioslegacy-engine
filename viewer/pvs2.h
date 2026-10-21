// PVS по курсу в горячих клетках (секция PV2S в конце level.shr, после PVS1; строит tools/pvs2.py). Для клетки PVS1 из таблицы горячих — 8 списков кусков по секторам
// курса камеры (45°, списки построены на ±42° от центра, гистерезис движка ±30°), вместо одного списка клетки. Остальные клетки — PVS1 как прежде.
// -DPVS_SECTOR_OLD=1 — как до правки (только PVS1). Чистый C99 без PSP-заголовков: проверка tests/pvs2/host.c.
// Формат (заголовок 32 Б): 'PV2S', u32 nhot, u32 nsec, u32 npool, u32 sig (FNV-1a по nv, затем ni всех кусков: другой экспорт уровня — секция не берётся), 12 Б нулей; u32 cell[nhot] (gz*W+gx сетки PVS1, по возрастанию); {u32 start, u32 n}[nhot*nsec]; u16 pool[npool].
#ifndef SHAR_PVS2_H
#define SHAR_PVS2_H
#include <math.h>
#include <string.h>
#ifndef PVS_SECTOR_OLD
#define PVS_SECTOR_OLD 0
#endif
#define PVS2_HALF 0.5235988f   // ±30°: пока курс не дальше от центра текущего сектора, сектор не меняется (гистерезис); сектор строился на ±42°
// сигнатура таблицы кусков (80 Б на запись: nv @32, ni @36): тот же расчёт, что tools/pvs2.py piece_sig
static unsigned pvs2Sig(const unsigned char *tab, unsigned npc) {
  unsigned h = 2166136261u; for (int f = 0; f < 2; f++) for (unsigned i = 0; i < npc; i++) { unsigned v; memcpy(&v, tab + 80u * i + (f ? 36u : 32u), 4); h = (h ^ v) * 16777619u; } return h;
}
typedef struct { unsigned nhot, nsec, npool; const unsigned *cell; const unsigned *sec; const unsigned short *pool; int ok; } Pvs2;
// блок целиком в памяти (size — длина); 0 — формат неверный, блок не используется
static int pvs2Init(Pvs2 *p, const void *blk, unsigned size, unsigned sig) {
  memset(p, 0, sizeof *p); if (!blk || size < 32 || memcmp(blk, "PV2S", 4)) return 0;
  const unsigned *u = (const unsigned *)blk; unsigned nh = u[1], ns = u[2], np = u[3];
  if (u[4] != sig || ns != 8 || nh > 65536u || np > (1u << 24)) return 0;
  unsigned long long need = 32ull + 4ull * nh + 8ull * nh * ns + 2ull * np; if (need > size) return 0;
  p->nhot = nh; p->nsec = ns; p->npool = np; p->cell = u + 8; p->sec = p->cell + nh; p->pool = (const unsigned short *)(p->sec + 2u * nh * ns);
  for (unsigned i = 1; i < nh; i++) if (p->cell[i - 1] >= p->cell[i]) { memset(p, 0, sizeof *p); return 0; }
  for (unsigned i = 0; i < nh * ns; i++) if ((unsigned long long)p->sec[2 * i] + p->sec[2 * i + 1] > np) { memset(p, 0, sizeof *p); return 0; }
  p->ok = 1; return 1;
}
static int pvs2Find(const Pvs2 *p, unsigned cell) {   // номер горячей клетки или -1
  if (!p->ok) return -1; int lo = 0, hi = (int)p->nhot - 1;
  while (lo <= hi) { int m = (lo + hi) >> 1; if (p->cell[m] == cell) return m; if (p->cell[m] < cell) lo = m + 1; else hi = m - 1; }
  return -1;
}
// сектор по курсу yaw (рад, атан2(x, z)) с гистерезисом: cur — прежний сектор (-1 нет)
static int pvs2Sector(float yaw, int cur) {
  const float step = 6.2831853f / 8.f;
  if (cur >= 0) { float d = yaw - cur * step; d -= 6.2831853f * floorf(d / 6.2831853f + .5f); if (fabsf(d) <= PVS2_HALF) return cur; }
  int s = (int)floorf(yaw / step + .5f); s %= 8; if (s < 0) s += 8; return s;
}
static int pvs2List(const Pvs2 *p, int hot, int sector, const unsigned short **out) {
  if (!p->ok || hot < 0 || (unsigned)hot >= p->nhot || sector < 0 || sector >= 8) return -1;
  const unsigned *e = p->sec + 2u * (unsigned)(hot * 8 + sector); *out = p->pool + e[0]; return (int)e[1];
}
#endif
