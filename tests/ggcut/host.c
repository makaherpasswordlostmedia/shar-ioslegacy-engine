// Побитовая сверка ggCutFast с ggCutRef (viewer/ge_guard.h, А4): случайные треугольники у камеры при разных ближних плоскостях и тангенсах; результат (число вершин и каждый float) обязан совпасть бит в бит.
//   cc -O2 -std=c99 -I viewer tests/ggcut/host.c -lm -o build/ggcut_host && build/ggcut_host
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ge_guard.h"
static unsigned s_ = 77; static float rnd(void) { s_ = s_ * 1664525u + 1013904223u; return (s_ >> 8) / 16777216.f; }
static void rv(GgV *v, float sc, float zmin, float zmax) {
  v->c[0] = (rnd() - .5f) * 2.f * sc; v->c[1] = (rnd() - .5f) * 2.f * sc * .6f; v->c[2] = zmin + rnd() * (zmax - zmin);
  for (int j = 0; j < 3; j++) v->l[j] = (rnd() - .5f) * 30.f; v->t[0] = rnd() * 65535; v->t[1] = rnd() * 65535; for (int j = 0; j < 4; j++) v->k[j] = rnd() * 255.f;
}
int main(void) {
  long n = 0, cut = 0, bad = 0, nz[9] = {0};
  const float zns[] = {.25f, .3f, .35f, .5f, .8f, 1.2f, 1.5f};
  for (int it = 0; it < 3000000; it++) {
    GgCam k = {.tvx = .55f + rnd() * .5f, .tvy = .3f + rnd() * .3f, .zn = zns[it % 7]};
    float sc = rnd() < .5f ? 3.f : 40.f; GgV t[3]; float zmax = rnd() < .5f ? 4.f : 25.f;
    for (int i = 0; i < 3; i++) rv(&t[i], sc, -2.f + rnd() * 2.f - 1.f, zmax);
    GgV o1[GG_MAXV], o2[GG_MAXV]; memset(o1, 0, sizeof o1); memset(o2, 0, sizeof o2);
    int n1 = ggCutRef(&t[0], &t[1], &t[2], &k, o1), n2 = ggCutFast(&t[0], &t[1], &t[2], &k, o2); n++;
    if (n1 != n2 || (n1 > 0 && memcmp(o1, o2, (size_t)n1 * sizeof(GgV)))) { bad++; if (bad < 4) printf("расхождение it=%d n1=%d n2=%d\n", it, n1, n2); }
    if (n1 >= 3) cut++; nz[n1 < 9 ? n1 : 8]++;
  }
  printf("треугольников %ld, непустых срезов %ld, по числу вершин: 0:%ld 3:%ld 4:%ld 5:%ld 6:%ld 7:%ld 8:%ld | расхождений %ld\n", n, cut, nz[0], nz[3], nz[4], nz[5], nz[6], nz[7], nz[8], bad);
  printf(bad ? "FAIL\n" : "OK\n"); return bad ? 1 : 0;
}
