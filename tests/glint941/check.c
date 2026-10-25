// №941 гейт геометрии общего шейпа блика (viewer/glintshape941.h, тот же код рисует spritelight.h и fx.c):
//   cc -I viewer tests/glint941/check.c -lm [-DGS_KSCALE=1.9f — красный: прямой ромб; -DGS_KSCALE=.3f — красный: тонкая игла]
// Для каждого шейпа (A, B, стекло, крест частиц): число лучей, кончики на заданных углах и длинах; боковая дуга ВОГНУТА (середина ближе к центру, чем середина хорды), гладкая
// (поворот контура на каждой вершине кроме кончика <= 30°, во впадине <= 25° — излома нет); угол при кончике <= 62° (по хорде на 1/8 стороны; у касательной меньше) (острый, не тупой ромб) и >= 20° (не игла);
// впадина .45-.66 радиуса кончика; бюджет вершин блика (веер: A 72, B 90 против 108 у лепестков №900) и звезды стекла (4n + 1 как у №937)
#include <stdio.h>
#include <math.h>
#include "glintshape941.h"
static int bad;
static void chk(int ok, const char *m, const char *nm, float v) { if (!ok) { printf("  FAIL %s: %s (%.2f)\n", nm, m, v); bad++; } }
int main(void) {
  struct { const char *nm; const GsDef *d; int seg; } L[] = {{"A", &GS_GLINT_A, 4}, {"B", &GS_GLINT_B, 4}, {"стекло", &GS_SPARK4, 5}, {"крест частиц", &GS_CROSS4, 3}};
  for (int s = 0; s < 4; s++) {
    const GsDef *d = L[s].d; float px[GS_MAXPTS], py[GS_MAXPTS], hx[GS_MAXPTS], hy[GS_MAXPTS];
    int m = gsOutline(d, L[s].seg, 1.f, px, py), mh = gsOutline(d, 8, 1.f, hx, hy), n = d->n;
    chk(m == n * L[s].seg, "число точек не n * seg", L[s].nm, (float)m);
    float tipmin = 9.f, tipmax = 0.f, valmin = 9.f, valmax = 0.f, turnv = 0.f, turno = 0.f, conc = 0.f;
    for (int i = 0; i < n; i++) {   // кончик i — точка i * seg
      int k = i * L[s].seg; float r = hypotf(px[k], py[k]); chk(fabsf(r - d->len[i]) < 1e-4f, "кончик не на своей длине", L[s].nm, r);
      if (r < tipmin) tipmin = r; if (r > tipmax) tipmax = r;
    }
    for (int i = 0; i < n; i++) {   // впадина — середина стороны (по плотному контуру: точка t = .5, индекс i * 8 + 4), сравнение с серединой хорды
      int k = i * 8 + 4, j = ((i + 1) % n) * 8; float cx = (hx[i * 8] + hx[j]) * .5f, cy = (hy[i * 8] + hy[j]) * .5f, rv = hypotf(hx[k], hy[k]), rc = hypotf(cx, cy);
      float lt = (d->len[i] + d->len[(i + 1) % n]) * .5f, ratio = rv / lt; if (ratio < valmin) valmin = ratio; if (ratio > valmax) valmax = ratio; if (rv / rc > conc) conc = rv / rc;
    }
    for (int i = 0; i < mh; i++) {   // поворот контура на вершине i
      int a = (i + mh - 1) % mh, b = (i + 1) % mh; float ax = hx[i] - hx[a], ay = hy[i] - hy[a], bx = hx[b] - hx[i], by = hy[b] - hy[i];
      float t = fabsf(atan2f(ax * by - ay * bx, ax * bx + ay * by)) * 57.29578f; int tip = i % 8 == 0, val = i % 8 == 4;
      if (tip) continue; if (val) { if (t > turnv) turnv = t; } else if (t > turno) turno = t;
    }
    float tipang = 999.f, tipangmin = 0.f;   // полный угол при кончике: между направлением на соседние точки (t = 1/8) по обе стороны
    for (int i = 0; i < n; i++) { int k = i * 8, p = (k + mh - 1) % mh, q = k + 1; float ax = hx[p] - hx[k], ay = hy[p] - hy[k], bx = hx[q] - hx[k], by = hy[q] - hy[k];
      float a = fabsf(atan2f(ax * by - ay * bx, ax * bx + ay * by)) * 57.29578f; if (a > tipangmin) tipangmin = a; if (a < tipang) tipang = a; }
    int verts = s >= 2 ? n * L[s].seg + 1 : n * 3 * (4 + 2);   // веер с индексами: центр + контур; блик spritelight — треугольники без индексов, шейп + сердцевина
    printf("%s: лучей %d, впадина %.2f..%.2f радиуса кончика (к хорде %.2f), поворот контура во впадине %.1f° / иначе %.1f°, угол при кончике %.0f..%.0f°, вершин на звезду %d\n",
           L[s].nm, n, valmin, valmax, conc, turnv, turno, tipang, tipangmin, verts);
    chk(valmin >= .45f && valmax <= .66f, "впадина вне .45-.66", L[s].nm, valmin);
    chk(conc < .88f, "бока не вогнуты (середина дуги не ближе к центру, чем середина хорды)", L[s].nm, conc);
    chk(turnv <= 25.f && turno <= 30.f, "излом контура", L[s].nm, turnv > turno ? turnv : turno);
    chk(tipangmin <= 62.f, "кончик тупой (угол > 62°)", L[s].nm, tipangmin);
    chk(tipang >= 20.f, "кончик-игла (угол < 20°)", L[s].nm, tipang);
    if (s < 2) chk(verts <= 108, "вершин на звезду больше, чем у лепестков №900 (108)", L[s].nm, (float)verts);
  }
  printf(bad ? "FAIL glint941 geometry\n" : "PASS glint941 geometry\n"); return bad ? 1 : 0;
}
