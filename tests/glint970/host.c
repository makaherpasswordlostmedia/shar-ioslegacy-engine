// №970: числа хода слоёв блика ключа (viewer/glintmotion970.h) на Маке. host НОВЫЙ|СТАРЫЙ -> строки; check.py читает.
// СТАРЫЙ — формулы TEST66 (gvAdd): kA 1 + .06 sin(tm/1.3), kB 1 + .12 sin(tm/.85 + .334), сдвиг (.06 sin(tm/1.1), .05 sin(tm/1.1 + .25)) · размер; tm = время % 60 с (шов при переходе).
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "../../viewer/glintmotion970.h"
static float gvSinT(float t) { float f = t - floorf(t); return sinf(6.2831853f * f); }
static void old66(float tm, float *kA, float *kB, float *wx, float *wy) {
  *kA = 1.f + .06f * gvSinT(tm / 1.3f); *kB = 1.f + .12f * gvSinT(tm / .85f + .3342254f);
  *wx = .06f * gvSinT(tm / 1.1f); *wy = .05f * gvSinT(tm / 1.1f + .25f);
}
int main(int argc, char **argv) {
  int isold = argc > 1 && !strcmp(argv[1], "old");
  // 120 с шагом 1/60 с (часы 0..60 дважды: шов на 60 с); phase ключа добавляется к tm — берём три разные
  static const float ph[3] = {0.f, 1.11f, 2.59f};
  for (int w = 0; w < 3; w++) {
    float prev[4] = {0}, pv[4] = {0}; int n = 0; double maxv[4] = {0}, maxa[4] = {0}, maxr = 0, seam = 0; double kmin[2] = {9, 9}, kmax[2] = {0, 0};
    for (int i = 0; i < 7200; i++) {
      float t = (float)(i % 3600) / 60.f + ph[w], v[4];   // часы идут по кругу 60 с
      if (isold) old66(t, &v[0], &v[1], &v[2], &v[3]); else gm970(t, &v[0], &v[1], &v[2], &v[3]);
      if (n) { for (int k = 0; k < 4; k++) { double d = v[k] - prev[k]; if (i == 3600) { if (fabs(d) > seam) seam = fabs(d); continue; } double vel = d * 60.0; if (fabs(vel) > maxv[k]) maxv[k] = fabs(vel);
          if (n > 1) { double a = (v[k] - 2.0 * prev[k] + pv[k]) * 3600.0; if (fabs(a) > maxa[k]) maxa[k] = fabs(a); } } }
      for (int k = 0; k < 2; k++) { if (v[k] < kmin[k]) kmin[k] = v[k]; if (v[k] > kmax[k]) kmax[k] = v[k]; }
      double r = sqrt((double)v[2] * v[2] + (double)v[3] * v[3]); if (r > maxr) maxr = r;
      memcpy(pv, prev, sizeof pv); memcpy(prev, v, sizeof prev); n++;
    }
    printf("HOST w=%d model=%s maxr=%.4f seam=%.5f vmax_x=%.4f vmax_y=%.4f amax_x=%.4f amax_y=%.4f kA=%.3f..%.3f kB=%.3f..%.3f\n", w, isold ? "old" : "new", maxr, seam, maxv[2], maxv[3], maxa[2], maxa[3], kmin[0], kmax[0], kmin[1], kmax[1]);
  }
  // ритм: сколько раз за 60 с сдвиг проходит ближе 0,3 от наибольшего (подход к центру) и доля времени, когда сдвиг ≤ 0,5 наибольшего
  { double rmax = 0; static float r[3600]; for (int i = 0; i < 3600; i++) { float v[4]; float t = (float)i / 60.f; if (isold) old66(t, &v[0], &v[1], &v[2], &v[3]); else gm970(t, &v[0], &v[1], &v[2], &v[3]); r[i] = sqrtf(v[2] * v[2] + v[3] * v[3]); if (r[i] > rmax) rmax = r[i]; }
    int near = 0; for (int i = 0; i < 3600; i++) if (r[i] <= .5f * rmax) near++;
    // автокорреляция kA на лаге 1…10 с: «случайнее» — нет повторов (максимум корреляции на лагах ≥ 1 с)
    double mean = 0, var = 0; static float a[3600]; for (int i = 0; i < 3600; i++) { float v[4]; float t = (float)i / 60.f; if (isold) old66(t, &v[0], &v[1], &v[2], &v[3]); else gm970(t, &v[0], &v[1], &v[2], &v[3]); a[i] = v[0]; mean += a[i]; } mean /= 3600;
    for (int i = 0; i < 3600; i++) var += (a[i] - mean) * (a[i] - mean);
    double best = -1; for (int lag = 60; lag <= 600; lag++) { double c = 0; for (int i = 0; i < 3600; i++) c += (a[i] - mean) * (a[(i + lag) % 3600] - mean); c /= var; if (c > best) best = c; }
    printf("HOST rhythm model=%s rmax=%.4f near_half=%.3f autocorr_1to10s=%.3f\n", isold ? "old" : "new", rmax, (double)near / 3600, best);
  }
  return 0;
}
