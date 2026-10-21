// Коды мест (правка Роба 58, 29.09: «коды, локации, аббревиатура, чтобы ты понимал ширину, долготу карты, где я нахожусь,
// куда правку нужно внедрять»). Код виден в служебном счётчике (строка 0) и называется голосом: «L1 D7-5».
//
// Сетка одна на все уровни, в координатах движка (level.shr: x как в игре, z игры зеркален), не зависит от сборки:
//   квадрат 100 м: столбец — буква по x от PC_X0 (A B C D E F G H J K L M, без I), ряд — число по z от PC_Z0 (1…15);
//   участок 33 м внутри квадрата — цифра 1…9 как на кнопках телефона: 1 2 3 — ряд с меньшим z, 7 8 9 — с большим.
// Границы — объединение карт радара всех уровней (resource/pure3d/l<N>hudmap.p3d, tools/ui_export.py bake_radar_map):
// x −607…444, z движка −670…783. Уровни 1/4/7 (одна карта) — один код = одно место. Обратный ход (код -> точка, ближайшие
// места по AddTeleportDest оригинала, лист карты с сеткой) — tools/place.py; то же правило, сверка — tests/placecode/gate.sh.
#ifndef PLACECODE_H
#define PLACECODE_H
#include <math.h>
#include <stdio.h>

#define PC_X0 -700.f
#define PC_Z0 -700.f
#define PC_CELL 100.f
#define PC_COLS 12
#define PC_ROWS 15
static const char PC_LETTERS[PC_COLS + 1] = "ABCDEFGHJKLM";

// x, z движка -> "D7-5"; за сеткой (трассы, края карты, за радаром) — код БЛИЖАЙШЕГО места на краю (№688: на трассе L2 был прочерк "--", Роб по коду пишет места);
// только не число (NaN) даёт "--"; out >= 8 байт
static inline void placeCode(float x, float z, char *out, int n) {
  float fx = (x - PC_X0) / PC_CELL, fz = (z - PC_Z0) / PC_CELL;
  if (!(fx == fx) || !(fz == fz)) { snprintf(out, n, "--"); return; }
  int c, r, sx, sz;
  if (fx < 0.f) { c = 0; sx = 0; } else if (fx >= (float)PC_COLS) { c = PC_COLS - 1; sx = 2; } else { c = (int)floorf(fx); sx = (int)floorf((fx - c) * 3.f); if (sx > 2) sx = 2; }
  if (fz < 0.f) { r = 0; sz = 0; } else if (fz >= (float)PC_ROWS) { r = PC_ROWS - 1; sz = 2; } else { r = (int)floorf(fz); sz = (int)floorf((fz - r) * 3.f); if (sz > 2) sz = 2; }
#ifdef PLACE_BREAK   // отрицательный контроль гейта: участок по кнопкам «снизу вверх» (7 8 9 сверху) — сверка обязана упасть
  sz = 2 - sz;
#endif
  snprintf(out, n, "%c%d-%d", PC_LETTERS[c], r + 1, 1 + sx + 3 * sz);
}
#endif
