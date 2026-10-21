// Правка Роба 304 (04.10, L1 H10-5: «кусты почему-то тормозят машину — прям затормаживают; доработать нормально»).
// Настоящая физика viewer/car.c + viewer/col.c на данных уровня, без эмулятора. Печатает по заезду строку
//   <вид> <номер> <скорость в конце, м/с> <интеграл доли кузова в листве, с>
// для каждого куста уровня (объёмы FOLIAGE: лежачие изгороди, кусты-ящики, шары):
//   par — вдоль куста в 0.5 м от его края (не касаясь), 15 м/с на газу, с обеих сторон; полоса без другой листвы ближе 0.3 м
//   crs — поперёк через середину куста накатом 12 м/с
//   h10 — путь из жалобы (эмулятор agent297_304a): тротуар вдоль ряда изгородей H10-5, полный газ 5.5 с
// tests/foliage/cover.sh собирает три варианта (новый, прежний -DFOLIAGE_DRAG_BOX=1 и опорный без вязкости -DFOLIAGE_DRAG=0)
// и сравнивает скорости заездов: вдоль куста — как у опорного (ложного торможения нет), поперёк — мягко (не ниже
// e^(−вязкость·(толщина + 0.5 м) / 6 м/с) от опорного).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld w; static Car car;

static int run(float x, float z, float h, float v0, float thr, float secs, float *vEnd, float *cov) {
  float g; if (!colGround(&w, x, z, 200.f, -200.f, &g, 0)) return 0;
  carInit(&car, 0, &w, x, g + 1.f, z, h); carSetSpeed(&car, v0);
  CarInput in = {thr, 0, 0, 0}; float c = 0.f, x0 = car.x, z0 = car.z;
  for (int n = 0; n < (int)(secs * 30.f); n++) { carUpdate(&car, &w, &in, 1.f / 30.f); c += car.foliCover / 30.f; }
  if (!isfinite(car.x) || hypotf(car.x - x0, car.z - z0) < 2.f) return 0;   // не сдвинулась со старта (зажата) — не заезд
  *vEnd = hypotf(car.vel[0], car.vel[2]); *cov = c; return 1;
}
// полоса свободна от листвы, кроме самого куста: точки по оси заезда на двух высотах, запас 0.3 м до кузова
static int laneFree(float x, float z, float ux, float uz, float len, float hw, float skipX, float skipZ, float skipR) {
  for (float s = 0.f; s <= len; s += .5f) {
    float px = x + ux * s, pz = z + uz * s, g;
    if (!colGround(&w, px, pz, 200.f, -200.f, &g, 0)) continue;
    for (float side = -hw - .3f; side <= hw + .3f; side += .35f) {
      float qx = px - uz * side, qz = pz + ux * side;
      if (hypotf(qx - skipX, qz - skipZ) < skipR) continue;
      if (colFoliageNear(&w, qx, g + .1f, qz, .3f) || colFoliageNear(&w, qx, g + 1.f, qz, .3f)) return 0;
    }
  }
  return 1;
}

int main(int argc, char **argv) {
  if (argc < 2) return 2; FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15); if (!data || fread(data, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&w, data + co, ce - co)) return 2;
  CarBox cb; carInit(&car, 0, &w, 0, 0, 0, 0); carBox(&car, &cb); const float hw = cb.hw;
  int id = 0; float v, c;
  for (unsigned k = 0; k < w.nbox + w.ncyl; k++) {
    float cx, cy, cz, ux, uz, Lu, Wv;   // центр, горизонтальная ось куста, полудлина вдоль неё и полутолщина поперёк
    if (k < w.nbox) {
      const ColBox *B = &w.box[k]; if (B->pad != 1.f) continue;
      const float *ax[3] = {B->ax, B->ay, B->az}; int a0 = -1;
      for (int i = 0; i < 3; i++) if (fabsf(ax[i][1]) < .5f && (a0 < 0 || B->h[i] > B->h[a0])) a0 = i;
      if (a0 < 0) continue;
      float l = hypotf(ax[a0][0], ax[a0][2]); ux = ax[a0][0] / l; uz = ax[a0][2] / l;
      Lu = Wv = 0.f;
      for (int i = 0; i < 3; i++) { Lu += B->h[i] * fabsf(ax[i][0] * ux + ax[i][2] * uz); Wv += B->h[i] * fabsf(-ax[i][0] * uz + ax[i][2] * ux); }
      cx = B->c[0]; cy = B->c[1]; cz = B->c[2];
    } else {
      const ColCyl *C = &w.cyl[k - w.nbox]; if (C->pad[0] != 1.f) continue;
      float l = hypotf(C->axis[0], C->axis[2]);
      if (C->halfLen > 0.f && l > .3f) { ux = C->axis[0] / l; uz = C->axis[2] / l; Lu = C->halfLen * l + C->r; } else { ux = 1.f; uz = 0.f; Lu = C->r; }
      Wv = C->r; cx = C->c[0]; cy = C->c[1]; cz = C->c[2];
    }
    (void)cy;
    float vx = -uz, vz = ux, len = 2.f * Lu + 12.f;
    for (int side = -1; side <= 1; side += 2) {   // вдоль, в 0.5 м от края
      float off = Wv + .5f + hw, sx = cx - ux * (Lu + 6.f) + vx * off * side, sz = cz - uz * (Lu + 6.f) + vz * off * side;
      id++;
      if (!laneFree(sx, sz, ux, uz, len, hw, cx, cz, hypotf(Lu, Wv) + .2f)) continue;
      if (run(sx, sz, atan2f(ux, uz), 15.f, 1.f, len / 15.f, &v, &c)) printf("par %d %.4f %.4f\n", id, v, c);
    }
    for (int side = -1; side <= 1; side += 2) {   // поперёк через середину
      float sx = cx - vx * (Wv + hw + 5.f) * side, sz = cz - vz * (Wv + hw + 5.f) * side;
      id++;
      if (run(sx, sz, atan2f(vx * side, vz * side), 12.f, 0.f, (2.f * Wv + 2.f * hw + 10.f) / 12.f, &v, &c))
        printf("crs %d %.4f %.4f %.3f\n", id, v, c, 2.f * Wv);
    }
  }
  // путь из жалобы (L1, эмулятор: 17 → 6 м/с на полном газу у ряда изгородей H10-5); на других уровнях здесь не L1 — без него
  if (argc > 2 && !strcmp(argv[2], "l1") && run(28.f, 237.f, 1.013f, 0.f, 1.f, 5.f, &v, &c)) printf("h10 0 %.4f %.4f\n", v, c);
  colFree(&w); free(data);
  return 0;
}
