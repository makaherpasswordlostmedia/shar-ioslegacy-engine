// Проверка: может ли разведение двух машин (carHitCar) протолкнуть лёгкую машину сквозь забор с лица на изнанку одним кадром.
//   fencepush level.shr X Z0 ... (забор вдоль x на z=Z0, лицо к +z; машины стоят на лицевой стороне, курс −z)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
static ColWorld w;
static int loadCol(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return -1; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return -1; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96);
  unsigned end = n; if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff);
  return colInit(&w, cm, end - colOff);
}
int main(int argc, char **argv) {
  if (argc < 4 || loadCol(argv[1])) { puts("usage: fencepush level.shr X Z0"); return 2; }
  float x = atof(argv[2]), z0 = atof(argv[3]), g; if (!colGround(&w, x, z0 + 3, 100, -1e5f, &g, 0)) { puts("нет земли"); return 2; }
  const char *names[2] = {"pickupa", "schoolbu"};
  for (int mb = 0; mb < 2; mb++) for (float gap = 0.f; gap <= 3.01f; gap += 0.5f) {   // gap — на сколько кузова перекрываются сверх касания
    CarParams pa, pb; carParamsFor("pickupa", &pa); carParamsFor(names[mb], &pb);
    Car a, b; float za = z0 + pa.halfL + 0.15f;
    carInit(&a, &pa, &w, x, g, za, 3.14159265f);
    float zb = za + pa.halfL + pb.halfL - gap;
    carInit(&b, &pb, &w, x, g, zb, 3.14159265f);
    float zA0 = a.z; int hit = carHitCar(&a, &b, &w);
    printf("пикап у забора + %-8s перекрытие %.1f м: hit=%d, пикап сдвинут на %.2f м (z %.2f → %.2f), забор на z=%.2f, %s\n", names[mb], gap, hit, a.z - zA0, zA0, a.z, z0, a.z < z0 ? "ЗА ЗАБОРОМ (проехал сквозь)" : "по эту сторону");
  }
  puts("--- один пикап, вдавленный в забор передом на emb м (центр кузова остаётся на лицевой стороне, пока emb < полудлины), 40 кадров без ввода");
  for (float emb = 0.3f; emb <= 3.01f; emb += 0.3f) {
    CarParams pa; carParamsFor("pickupa", &pa); Car a; float za = z0 + pa.halfL - emb + pa.bodyOfs * 0.f;
    carInit(&a, &pa, &w, x, g, za, 3.14159265f);
    float zs = a.z; CarInput in = {0}; float zmin = a.z; int rev0 = a.reverts;
    for (int t = 0; t < 40; t++) { carUpdate(&a, &w, &in, 1.f / 60); if (a.z < zmin) zmin = a.z; }
    printf("вдавлен на %.1f м: z %.2f → %.2f (мин %.2f), reverts+%d, забор z=%.2f: %s\n", emb, zs, a.z, zmin, a.reverts - rev0, z0, a.z < z0 - 0.3f ? "ЗА ЗАБОРОМ" : "по эту сторону");
  }
  puts("--- глубина проникновения кузова пикапа в забор, когда центр на линии забора (так колёса ищут точку выхода, escapeOutEx): колонки — z центра");
  { CarParams pa; carParamsFor("pickupa", &pa); Car a; carInit(&a, &pa, &w, x - 6.f, g, z0 + 8.f, -0.984f);
    for (float dz = 3.f; dz >= -3.01f; dz -= 0.5f) { a.x = x; a.z = z0 + dz; a.y = g; CarBox b; carBox(&a, &b); colProbeCar(&w, &b);
      printf("центр z=%.2f (забор z=%.2f, dz=%+.1f): n=%d maxDepth=%.2f", a.z, z0, dz, b.n, b.maxDepth); for (int q = 0; q < b.n; q++) printf(" [%d#%u d=%.2f]", b.type[q], b.index[q], b.depth[q]); puts(""); } }
  return 0;
}
