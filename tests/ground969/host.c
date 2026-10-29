// №969 хост-проверка зерна земли (viewer/ground969.h): без движка и эмулятора. host [red]
//   Проверки: детерминизм (два построения совпадают побайтно), 16 уровней поровну, контраст в пределах amp, нет пятен: разброс средних по блокам 8x8 не больше 0,35 от разброса точек (зерно только высоких частот).
//   «red» — красный контроль: поле заменено сглаженным шумом (низкие частоты) -> проверка «нет пятен» обязана упасть. Последняя строка PASS / FAIL
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "../../viewer/ground969.h"
static float blockRatio(const float *f) {
  double m = 0, s = 0; int n = GD_W * GD_W; for (int i = 0; i < n; i++) m += f[i]; m /= n; for (int i = 0; i < n; i++) s += (f[i] - m) * (f[i] - m); s = sqrt(s / n);
  double bs = 0; int nb = 0; for (int by = 0; by < GD_W; by += 8) for (int bx = 0; bx < GD_W; bx += 8) { double a = 0; for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) a += f[(by + y) * GD_W + bx + x]; a /= 64; bs += (a - m) * (a - m); nb++; }
  return (float)(sqrt(bs / nb) / (s > 1e-9 ? s : 1e-9));
}
int main(int argc, char **argv) {
  int red = argc > 1 && !strcmp(argv[1], "red"), bad = 0;
  for (int cls = 1; cls <= 2; cls++) for (int st = 1; st <= 2; st++) {
    GdPar p = gdPar(cls, st); float f[GD_W * GD_W], g[GD_W * GD_W], mean, mean2; gdField(f, cls, p.amp, &mean); gdField(g, cls, p.amp, &mean2);
    int same = !memcmp(f, g, sizeof f);
    if (red) { for (int y = 0; y < GD_W; y++) for (int x = 0; x < GD_W; x++) { float a = 0; for (int dy = -6; dy <= 6; dy++) for (int dx = -6; dx <= 6; dx++) a += f[((y + dy + GD_W) % GD_W) * GD_W + (x + dx + GD_W) % GD_W]; g[y * GD_W + x] = 1.f - (1.f - a / 169.f) * 6.f; } memcpy(f, g, sizeof f); }
    int lv[16] = {0}; float lo = 9, hi = -9; for (int i = 0; i < GD_W * GD_W; i++) { if (f[i] < lo) lo = f[i]; if (f[i] > hi) hi = f[i]; int q = (int)((1.f - f[i]) / p.amp * 15.99f); if (q < 0) q = 0; if (q > 15) q = 15; lv[q]++; }
    int flat = 1; for (int i = 0; i < 16; i++) if (lv[i] < 200 || lv[i] > 312) flat = 0;
    float br = blockRatio(f); int ok = same && flat && lo >= 1.f - p.amp - 1e-4f && hi <= 1.f + 1e-4f && br <= .35f;
    printf("  %s cls=%d style=%d pitch=%.1f amp=%.2f mean=%.3f уровней поровну=%d блоки/точки=%.2f (нужно <= 0,35) детерминизм=%d\n", ok ? "ok  " : "FAIL", cls, st, p.pitch, p.amp, mean, flat, br, same);
    if (!ok) bad++;
  }
  puts(bad ? "FAIL" : "PASS"); return bad ? 1 : 0;
}
