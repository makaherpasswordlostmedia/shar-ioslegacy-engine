// №976: числа хода столба звёзд цели (viewer/glintmotion976.h) и ровности кольца на Маке. host new|old -> строки HOST976; check.py читает.
// old — формулы TEST66 (collectfx.c): h = min(12, 25 t); a = min(1, t/.1) · (t > .65 ? (.9 - t)/.25 : 1); звезда на высоте y: a сразу целиком, когда фронт её прошёл.
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "../../viewer/glintmotion976.h"
#define H 12.f
#define LIFE .9f
static void colOld(float t, float *h, float *a, float *rad) { *h = fminf(H, 25.f * t); *a = fminf(1.f, t / .1f) * (t > .65f ? fmaxf(0.f, (LIFE - t) / (LIFE - .65f)) : 1.f); *rad = .35f; }
static float starOld(float a, float h, float y) { return y < h ? a : 0.f; }
int main(int argc, char **argv) {
  int old = argc > 1 && !strcmp(argv[1], "old"); float dt = 1.f / 60.f;
  double maxA = 0, maxdh = 0, maxddh = 0, maxda = 0, maxstar = 0, maxstep = 0, pk = 0, prevh = 0, prevv = 0, preva = 0, pr = 0, maxdr = 0;
  float prevStar[40]; memset(prevStar, 0, sizeof prevStar); int n = 0;
  for (float t = 0.f; t <= LIFE; t += dt, n++) {
    float h, a, rad; if (old) colOld(t, &h, &a, &rad); else gm976Col(t, H, LIFE, &h, &a, &rad);
    double v = (h - prevh) / dt, acc = n > 1 ? (v - prevv) / dt : 0; if (n > 0) { if (fabs(v) > maxdh) maxdh = fabs(v); if (n > 1 && fabs(acc) > maxddh) maxddh = fabs(acc); }
    if (n > 0) { double da = fabs(a - preva); if (da > maxda) maxda = da; double dr = fabs(rad - pr); if (dr > maxdr) maxdr = dr; }
    for (int k = 0; k < 18; k++) { float y = .7f * k, s = old ? starOld(a, h, y) : gm976Star(a, h, y); s *= old ? 1.f : COL976_A; if (s > pk) pk = s;
      if (n > 0) { double d = fabs(s - prevStar[k]); if (d > maxstep) maxstep = d; } prevStar[k] = s; }
    if (a * (old ? 1.f : COL976_A) > maxA) maxA = a * (old ? 1.f : COL976_A);
    prevh = h; prevv = v; preva = a; pr = rad;
  }
  // кольцо цели: прогиб многоугольника из N сторон, доля радиуса
  float N = old ? 18.f : (float)SPHERE976_N, sag = 1.f - cosf(3.14159265f / N);
  printf("HOST976 model=%s peak_alpha=%.3f vmax=%.2f accel_max=%.1f alpha_step=%.4f star_step=%.4f radius_step=%.4f sag=%.5f\n", old ? "old" : "new", pk, maxdh, maxddh, maxda, maxstep, maxdr, sag);
  return 0;
}
