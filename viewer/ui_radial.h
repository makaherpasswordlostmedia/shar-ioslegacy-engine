// Pure geometry shared by the PSP renderer and the host pixel/coverage checks.
#ifndef SHAR_UI_RADIAL_H
#define SHAR_UI_RADIAL_H
#include <math.h>
typedef struct { float u, v; } UiRadialPoint;
#define UI_RADIAL_MAX 66
// Дуга шкалы Hit & Run по оригиналу (правка Роба 241, 03.10): конец заливки = 21.3° + 3.13°·шкала по часовой от 12 часов —
// 0 под красной половиной мигалки, 100 — 334° под синей, наверху зазор 47° под мигалкой. Замер: близнецы b3_chase кадры
// 1400/1200/1000/820 и tw_v8_stand 400 (шкала 19.3/43.3/67.3/88.8/70.6 -> 82/160/235/300/245°, разброс ±1.5°); запись PS2:
// спад 3/с идёт 9.1–9.6°/с, в погоне 6/с — 18.8°/с (3.1°/ед.); порог предупреждения 78 — 265° («без четверти»)
#define UI_RADIAL_A0   0.37175513f   // 21.3°
#define UI_RADIAL_SPAN 5.46288056f   // 313°
static inline int uiRadialFan(int value, UiRadialPoint *p) {
  if (value <= 0) return 0;
  if (value > 1000) value = 1000;
  int steps = (value * 64 + 999) / 1000;
  p[0] = (UiRadialPoint){.5f, .5f};
  for (int i = 0; i <= steps; i++) {
    float a = -1.5707963267949f + UI_RADIAL_A0 + UI_RADIAL_SPAN * (value / 1000.f) * i / steps;
    p[i + 1] = (UiRadialPoint){.5f + .5f * cosf(a), .5f + .5f * sinf(a)};
  }
  return steps + 2;
}
#endif
