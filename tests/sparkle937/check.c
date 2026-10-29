// №937 гейт формы звезды-sparkle ✨ (Роб: «блинг-блинг, как эмодзи»): контур из viewer/sparkle937.h, тот же код, что рисует viewer/fx.c.
//   cc -I viewer tests/sparkle937/check.c -lm [-DFX_SPK_P=1.f — красный: прямые бока ромба, как у звезды-снежинки №923; -DFXD_POP_OVER=1.f — красный: поп без перелёта]
// 1. ровно четыре кончика (локальные максимумы радиуса) — на осях (±3°); 2. бока вогнутые: радиус на 45° ≤ .55 (у ромба .707); 3. кончики тонкие: полуширина на 90 % длины
// луча ≤ .06 (у ромба .10); 4. вертикальный луч 1,0, горизонтальный FX_SPK_HX .8–.9; малые звёзды .3–.4 главной; контур замкнут и без самопересечений по порядку углов.
#include <stdio.h>
#include <math.h>
#include "sparkle937.h"
#include "fxdsp.h"
int main(void) {
  float px[4 * SPK_MAXN + 1], py[4 * SPK_MAXN + 1]; int n = FX_SPK_N, m = spkOutline(px, py, n) - 1, bad = 0;
  float r[4 * SPK_MAXN], ang[4 * SPK_MAXN];
  for (int i = 0; i < m; i++) { r[i] = hypotf(px[i], py[i]); ang[i] = atan2f(py[i], px[i]); if (ang[i] < 0) ang[i] += 6.2831853f; }
  int tips = 0; float tipErr = 0.f;
  for (int i = 0; i < m; i++) { float a = r[(i + m - 1) % m], b = r[i], c = r[(i + 1) % m];
    if (b > a + 1e-5f && b >= c && b > .9f) { tips++; float q = fmodf(ang[i] * 57.29578f + 360.f, 90.f); q = q > 45.f ? 90.f - q : q; if (q > tipErr) tipErr = q; } }
  float rmin = 9.f; for (int i = 0; i < m; i++) if (r[i] < rmin) rmin = r[i];   // самая глубокая точка бока (у ромба .707, у sparkle около .4)
  float w90 = 0.f;   // полуширина луча на 90 % длины: пересечение контура (по рёбрам, не по точкам) с x = .9 у правого кончика
  for (int i = 0; i < m; i++) { float x0 = px[i], x1 = px[(i + 1) % m]; if (px[i] >= 0 && px[(i + 1) % m] >= 0 && ((x0 - .9f) * (x1 - .9f) <= 0.f) && x0 != x1) { float u = (.9f - x0) / (x1 - x0), y = fabsf(py[i] + (py[(i + 1) % m] - py[i]) * u); if (y > w90) w90 = y; } }
  int mono = 1; for (int i = 1; i < m; i++) if (ang[i] < ang[i - 1] - 1e-4f) mono = 0;
  int verts = 1 + 4 * FX_SPK_N + 3 * (1 + 4 * FX_SPK_N2), idx = 12 * FX_SPK_N + 36 * FX_SPK_N2;
  printf("n=%d: кончиков %d (от осей %.1f°), самая глубокая точка бока %.2f, полуширина на 90%% луча %.3f, замкнут %d, обход по порядку %d, на звезду %d вершин и %d индексов\n", n, tips, tipErr, rmin, w90, fabsf(px[m] - px[0]) + fabsf(py[m] - py[0]) < 1e-6f, mono, verts, idx);
  if (tips != 4) { printf("FAIL кончиков не 4\n"); bad++; }
  if (tipErr > 3.f) { printf("FAIL кончики не на осях\n"); bad++; }
  if (!(rmin <= .55f)) { printf("FAIL бока не вогнутые (радиус на глубине бока %.2f > .55)\n", rmin); bad++; }
  if (!(w90 > 0.f && w90 <= .06f)) { printf("FAIL кончики толстые или не измерены (%.3f, нужно 0..0,06)\n", w90); bad++; }
  if (!(FX_SPK_HX >= .8f && FX_SPK_HX <= .9f)) { printf("FAIL горизонтальный луч %.2f\n", FX_SPK_HX); bad++; }
  if (!(FX_SPK_SAT >= .3f && FX_SPK_SAT <= .4f)) { printf("FAIL малые звёзды %.2f\n", FX_SPK_SAT); bad++; }
  if (!mono) { printf("FAIL контур не по порядку\n"); bad++; }
  if (verts > 64 || idx > 180) { printf("FAIL на звезду %d вершин / %d индексов (бюджет GE: не больше 64 / 180; v2 было 240 вершин)\n", verts, idx); bad++; }
  // кривая попа (fxdsp.h fxdPop): 0 в нуле, наибольшее FXD_POP_OVER (1,15) около T1, 1 к T2 (0,12–0,15 с) и дальше, без скачков (шаг 5 мс — не больше .2)
  { float mx = 0.f, prev = 0.f, jump = 0.f, tmax = 0.f; for (int i = 0; i <= 400; i++) { float a = i * .005f, k = fxdPop(a); if (k > mx) { mx = k; tmax = a; } if (i && fabsf(k - prev) > jump) jump = fabsf(k - prev); prev = k; }
    printf("поп: в 0 с %.2f, наибольшее %.2f в %.3f с, в T2 (%.2f с) %.3f, дальше %.3f, наибольший шаг %.3f\n", fxdPop(0.f), mx, tmax, FXD_POP_T2, fxdPop(FXD_POP_T2), fxdPop(.5f), jump);
    if (fxdPop(0.f) != 0.f) { printf("FAIL поп не с нуля\n"); bad++; }
    if (!(mx >= 1.14f && mx <= 1.16f)) { printf("FAIL наибольшее %.2f не 1,15\n", mx); bad++; }
    if (!(FXD_POP_T2 >= .12f && FXD_POP_T2 <= .15f)) { printf("FAIL поп длится %.2f с (0,12–0,15)\n", FXD_POP_T2); bad++; }
    if (fabsf(fxdPop(FXD_POP_T2) - 1.f) > .01f || fabsf(fxdPop(.5f) - 1.f) > 1e-6f) { printf("FAIL после попа не 1\n"); bad++; }
    if (jump > .2f) { printf("FAIL кривая со скачком %.3f\n", jump); bad++; } }
  printf(bad ? "FAIL sparkle937\n" : "PASS sparkle937\n"); return bad ? 1 : 0;
}
