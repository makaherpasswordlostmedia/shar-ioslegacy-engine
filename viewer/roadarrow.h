// №606: высота набора зелёных стрелок на дороге (общий код игры и хост-гейта tests/roadarrow/). Точка пути — узел дороги трафика со своей высотой;
// асфальт под набором (три стрелки через 4 м вдоль курса, ±7,5 м) на склоне, бугре, мосту бывает выше — стрелка уходит под дорогу. Берём самую высокую
// точку коллизии под набором и поднимаем на неё + RA_LIFT. ground(x, z, yHi, yLo, &y) — высота коллизии (colGround), 1 — найдена.
#ifndef SHAR_ROADARROW_H
#define SHAR_ROADARROW_H
#include <math.h>
#ifndef RA_LIFT
#define RA_LIFT .06f
#endif
typedef int (*RaGround)(float x, float z, float yHi, float yLo, float *out);
static inline float raTop(RaGround ground, const float P[3], float heading) {   // самая высокая точка коллизии под набором; −1e9 — нигде не нашли
  float sh = sinf(heading), ch = cosf(heading), top = -1e9f;
  if (!ground) return top;
  for (int k = -3; k <= 3; k++) { float g, d = k * 2.5f; if (ground(P[0] + sh * d, P[2] + ch * d, P[1] + 4.f, P[1] - 8.f, &g) && g > top) top = g; }
  return top;
}
static inline float raLiftedY(RaGround ground, const float P[3], float heading) {
  float top = raTop(ground, P, heading);
  return top > -1e8f ? top + RA_LIFT : P[1] + RA_LIFT;
}
#endif
