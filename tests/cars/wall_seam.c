// №687: скользящий контакт по ровной стене сохраняет скорость, шов соседних кусков не цепляет. Синтетика: плоская земля и стена x = 30 из двух кусков
// (треугольники) со швом при z = 0: вариант 0 — впритык, 1 — зазор 2 см, 2 — перекрытие 5 см, 3 — ступенька 3 см (второй кусок глубже в стену), 4 — ступенька
// 3 см наружу (на дорогу), 5 — нормали второго куска отклонены на 2° . Машины famil_v, schoolbu, marge_v; углы 5/15/30°, скорость 10 и 25 м/с, едет к шву с обеих сторон.
// Провал: не прошла 40 м вдоль стены за 8 с или скорость в конце < 0,45·v·cos(угла). Код возврата 1 при провале.
// cc -std=c11 -O2 -I viewer tests/cars/wall_seam.c viewer/car.c viewer/col.c -lm -o wall_seam
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "carparams.h"
static struct { ColHdr h; ColTri t[6]; unsigned start[2], refs[6]; } fl;
static ColWorld w;
static void quad(int i, float x0, float x1, float xa, float xb, float z0, float z1, float nx, float nz) {   // стена: плоскость от (xa,z0)-(xb,z1), низ -5, верх 40
  fl.t[i] = (ColTri){{xa, -5, z0}, {xb, 40, z1}, {xb, -5, z1}, {nx, 0, nz}}; fl.t[i + 1] = (ColTri){{xa, -5, z0}, {xa, 40, z0}, {xb, 40, z1}, {nx, 0, nz}}; (void)x0; (void)x1;
}
int main(void) {
  const char *cars[3] = {"famil_v", "schoolbu", "marge_v"}; const float angs[3] = {5, 15, 30}, vts[2] = {10, 25};
  const char *vn[6] = {"впритык", "зазор 2 см", "перекрытие 5 см", "ступенька в стену 3 см", "ступенька на дорогу 3 см", "нормаль +2°"};
  int bad = 0, runs = 0;
  for (int var = 0; var < 6; var++) {
    memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = 6; fl.h.nref = 6;
    fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}}; fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
    float stp = getenv("STEP") ? atof(getenv("STEP")) : 0.03f;
    float zs = var == 1 ? -0.02f : var == 2 ? 0.05f : 0.f, x2 = var == 3 ? 30.f + stp : var == 4 ? 30.f - stp : 30.f, nz2 = var == 5 ? 0.0349f : 0.f;
    float nl = hypotf(1.f, nz2);
    quad(2, 0, 0, 30, 30, -2000, 0 + zs, -1, 0);                   // первый кусок: z от -2000 до 0
    quad(4, 0, 0, x2, x2, 0 - zs * (var == 2 ? 1 : 1), 2000, -1.f / nl, nz2 / nl);   // второй: от 0 до 2000
    fl.start[1] = 6; for (int i = 0; i < 6; i++) fl.refs[i] = i;
    if (colInit(&w, &fl, sizeof fl)) return 2;
    for (int m = 0; m < 3; m++) for (int ia = 0; ia < 3; ia++) for (int iv = 0; iv < 2; iv++) for (int d = -1; d <= 1; d += 2) {
      CarParams p; carParamsFor(cars[m], &p); float th = angs[ia] * 0.0174533f, vt = vts[iv];
      float fz = d * cosf(th), fx = sinf(th);                      // едем вдоль ±z, к стене (+x)
      Car c; float sz = -d * 30.f; carInit(&c, &p, &w, 30.f - 2.f - 12.f * tanf(th), 0, sz, atan2f(fx, fz));
      for (int i = 0; i < 30; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 60);
      carSetSpeed(&c, vt); float z0 = c.z, vmin = 1e9; int hit = 0; float t = 0;
      for (; t < 8.f; t += 1.f / 60) {
        CarInput in = {0}; in.throttle = c.v < vt ? 1.f : 0.f; carUpdate(&c, &w, &in, 1.f / 60);
        if (c.wallV > .3f) hit = 1;
        float al = (c.z - z0) * d; if (hit && al > 10.f && al < 55.f) { float vv = hypotf(c.vel[0], c.vel[2]); if (vv < vmin) vmin = vv; }
        if (getenv("DBG") && var == atoi(getenv("DBG")) && m == 0 && ia == 2 && iv == 0 && d == 1 && (c.z - z0) * d > 24.f && (c.z - z0) * d < 31.f) printf("  t=%.2f al=%.2f x=%.3f z=%.3f v=%.1f wallV=%.1f h=%.0f rev=%d why=%d dmg=%.3f\n", t, (c.z - z0) * d, c.x, c.z, hypotf(c.vel[0], c.vel[2]), c.wallV, c.h * 57.3f, c.reverts, c.revWhy, c.damage);
        if ((c.z - z0) * d > 62.f) break;
      }
      runs++;
      if (!hit) continue;
      int ok = (c.z - z0) * d > 60.f && vmin >= .45f * vt * cosf(th) && fabsf(c.roll) < 1.f;
      if (!ok) { bad++; printf("FAIL %s %s %.0f° %.0f м/с %s: вдоль %.1f м, vmin %.1f (ждали ≥ %.1f), крен %.0f°\n", vn[var], cars[m], angs[ia], vt, d > 0 ? "+z" : "-z", (c.z - z0) * d, vmin, .45f * vt * cosf(th), c.roll * 57.3f); }
    }
  }
  printf("RESULT %s (%d провалов из %d заездов)\n", bad ? "FAIL" : "PASS", bad, runs);
  return bad ? 1 : 0;
}
