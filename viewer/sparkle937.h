// №937: контур звезды-sparkle ✨ (чистая математика, без PSP — тот же код в viewer/fx.c и в гейте tests/sparkle937). Четыре дуги суперэллипса |x|^p + |y|^p = 1 (p < 1:
// бока вогнутые, кончики острые), по n точек на дугу, гуще у кончиков; обход против часовой от правого кончика. Кончики лежат на осях (радиус 1); x, y — единичный круг
#ifndef SPARKLE937_H
#define SPARKLE937_H
#include <math.h>
#ifndef FX_SPK_P
#define FX_SPK_P .55f        // показатель суперэллипса: меньше — тоньше кончики и глубже бока
#endif
#define SPK_MAXN 12
#ifndef FX_SPK_N
#define FX_SPK_N 5           // отрезков на дугу главной звезды (v2: 8); кончики сэмплируются гуще
#endif
#ifndef FX_SPK_N2
#define FX_SPK_N2 3          // то же у сердцевины и малых звёзд (v2: 4)
#endif
#define FX_SPK_MAXQ 16       // полных звёзд (с сердцевиной и спутниками) на группу кадра; остальные — только главная
#define FX_SPK_R .78f        // вертикальный радиус главной звезды (доля полуоси квада)
#define FX_SPK_HX .85f       // горизонтальный луч / вертикальный
#define FX_SPK_SAT .35f      // малые звёзды / главная
#define FX_SPK_CORE .40f     // сердцевина / главная
static inline int spkOutline(float *px, float *py, int n) {   // px, py: 4 * SPK_MAXN + 1; -> число точек (замкнуто: последняя = первая)
  if (n > SPK_MAXN) n = SPK_MAXN; int m = 0;
  for (int quad = 0; quad < 4; quad++) for (int k = 0; k < n; k++) {
    float u = (float)k / (float)n, t = (.5f - .5f * cosf(3.14159265f * u)) * 1.57079633f;   // гуще у кончиков (оси)
    if (quad & 1) t = 1.57079633f - t;                                                      // дуга идёт от оси к оси
    float ca = fabsf(cosf(t)), sa = fabsf(sinf(t)), r = powf(powf(ca, FX_SPK_P) + powf(sa, FX_SPK_P), -1.f / FX_SPK_P);   // fabsf: cos(π/2) бывает -4e-8, powf отрицательного — NaN
    float x = r * ca, y = r * sa;
    if (quad == 1) { x = -x; } else if (quad == 2) { x = -x; y = -y; } else if (quad == 3) { y = -y; }
    px[m] = x; py[m] = y; m++;
  }
  px[m] = px[0]; py[m] = py[0];
  return m + 1;
}
#endif
