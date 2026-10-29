// levlight.h — свет уровня для освещаемых объектов (29.09, docs/РЕЦЕПТ_УРОВНЯ.md §12). Только заголовок: читают движок
// (main.c, skin.c) и проверки на Маке (tests/light/*host.c).
//
// В оригинале мир запечён в цвет вершин (шейдеры мира без LIT, у вершин свой цвет) — ночь и закат уровня уже в геометрии.
// На ходу освещаются только объекты с шейдером LIT 1 без цвета вершин: машины, персонажи и редкие предметы. Их свет —
// группа LightGroup "sun" в art/l<N>_terra.p3d: 1 фоновый + 3 направленных источника. Экспорт (tools/level_light.py)
// кладёт её в блок LGT1 в конце секции CAR1 версии 3 (сразу за блоком машины: смещение CAR1 @24 + длина @28):
//   0   'LGT1'
//   4   u32 версия (1)
//   8   u32 уровень
//   12  u32 направленных источников n (до 4, включённые)
//   16  u32 фоновый ABGR (цвет с диска)
//   20  4 x { f32 x, y, z — единичный вектор НА источник, оси level.shr (z отзеркален); u32 ABGR с диска }
//   84  f32 ambS[3] — множитель фоновой части формы порта, по каналам R, G, B
//   96  f32 dirS[3] — множитель направленной части, R, G, B (сейчас оба = средняя освещённость уровня N / уровня 1:
//                     фон + ¼ Σ направленных, tools/level_light.py)
//   108 u32 FNV-1a 32 байт 0..107 (целостность)
//   112 char группа[16] ("sun")
// Правило порта (форма света): машины запечены экспортом (psp_export.car_prims: CAR_AMB × ambS + CAR_DIF × dirS по нормали),
// персонажи — солнце SKIN_SUN_ABGR × dirS и фон SKIN_AMB_ABGR × ambS (viewer/skin.h, skinLightLevel). Уровень 1: множители 1.
#ifndef LEVLIGHT_H
#define LEVLIGHT_H
#include <string.h>

#define LGT1_LEN 128
typedef struct {
  unsigned level, ndir, amb;
  float dir[4][3]; unsigned col[4];
  float ambS[3], dirS[3];
  char group[17];
} LevLight;

static inline unsigned levLightFnv(const unsigned char *b, unsigned n) {
  unsigned h = 2166136261u;
  for (unsigned i = 0; i < n; i++) { h ^= b[i]; h *= 16777619u; }
  return h;
}
static inline int levLightSane(float v) { return v == v && v >= 0.f && v <= 4.f; }
// sec — секция CAR1 целиком (size байт). 1 — блок прочитан; 0 — CAR1 версии < 3 (света нет: свет уровня 1);
// < 0 — битый блок (-1 не CAR1, -2 за концом секции, -3 не LGT1/версия, -4 контрольная сумма, -5 числа вне разумного)
static inline int levLightParse(const void *sec, unsigned size, LevLight *L) {
  memset(L, 0, sizeof *L);
  const unsigned char *b = (const unsigned char *)sec;
  if (!b || size < 32 || memcmp(b, "CAR1", 4)) return -1;
  unsigned u[7]; memcpy(u, b + 4, sizeof u);
  if (u[0] < 3) return 0;
  unsigned off = u[5] + u[6];
  if (u[5] < 32 || off < u[5] || off > size || size - off < LGT1_LEN) return -2;
  const unsigned char *q = b + off;
  unsigned v[4]; memcpy(v, q + 4, sizeof v);
  if (memcmp(q, "LGT1", 4) || v[0] != 1) return -3;
  unsigned h; memcpy(&h, q + 108, 4);
  if (h != levLightFnv(q, 108)) return -4;
  L->level = v[1]; L->ndir = v[2]; L->amb = v[3];
  if (L->ndir > 4) return -5;
  for (int i = 0; i < 4; i++) { memcpy(L->dir[i], q + 20 + 16 * i, 12); memcpy(&L->col[i], q + 32 + 16 * i, 4); }
  memcpy(L->ambS, q + 84, 12); memcpy(L->dirS, q + 96, 12);
  memcpy(L->group, q + 112, 16); L->group[16] = 0;
  for (int c = 0; c < 3; c++) if (!levLightSane(L->ambS[c]) || !levLightSane(L->dirS[c])) return -5;
  return 1;
}
static inline const char *levLightError(int e) {
  switch (e) {
    case 1: return "свет уровня из LGT1"; case 0: return "CAR1 без LGT1: свет уровня 1";
    case -1: return "не секция CAR1"; case -2: return "LGT1 за концом секции"; case -3: return "не LGT1";
    case -4: return "LGT1 битый (сумма)"; case -5: return "LGT1: числа вне разумного";
  }
  return "?";
}
// ABGR × (R, G, B) с округлением и потолком 255; альфа как была
static inline unsigned levLightScale(unsigned abgr, const float s[3]) {
  unsigned out = abgr & 0xff000000u;
  for (int c = 0; c < 3; c++) {
    float v = (float)((abgr >> (8 * c)) & 0xff) * s[c] + .5f;
    unsigned k = v >= 255.f ? 255u : v <= 0.f ? 0u : (unsigned)v;
    out |= k << (8 * c);
  }
  return out;
}
#endif
