// Заезд машины на трамплины и горки на хосте (тот же col.c и car.c, что в игре): для каждой строки stdin «tag x y z heading kmh tx tz [secs]» едет от (x, z) на опоре около высоты y курсом heading
// с постоянной скоростью kmh к цели (tx, tz) и печатает итог: дошла ли (в 4 м от цели, не ниже 60 % скорости), первый удар о препятствие (скорость удара, кадр, место, номера примитивов).
// Заезды с недостижимого старта (нет земли, скачок земли больше 1,2 м на 2 м пути в первые 20 м) помечаются SKIP.
//   rampsim level.shr < случаи
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
static ColWorld w; static Car car;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96); unsigned end = n;
  if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff); if (colInit(&w, cm, end - colOff)) { puts("col fail"); return 1; }
  char line[512], tag[64];
  while (fgets(line, sizeof line, stdin)) {
    float x, y, z, h, kmh, tx, tz, secs = 8; int k = sscanf(line, "%63s %f %f %f %f %f %f %f %f", tag, &x, &y, &z, &h, &kmh, &tx, &tz, &secs); if (k < 8) continue;
    float g0, fx = sinf(h), fz = cosf(h); if (!colGround(&w, x, z, y + 1.5f, y - 3.f, &g0, 0)) { printf("%s SKIP no_ground\n", tag); continue; }
    int bad = 0; float pg = g0;   // достижимость: земля непрерывна первые 20 м (ищем от самой нижней опоры к машине: беру опору, ближайшую к предыдущей)
    for (float s = 2; s <= 20; s += 2) { float gg; if (!colGroundMat(&w, x + fx * s, z + fz * s, pg + 1.2f, pg - 1.2f, &gg, 0, 0)) { bad = 1; break; } pg = gg; }
    if (bad) { printf("%s SKIP discontinuous\n", tag); continue; }
    carInit(&car, NULL, &w, x, g0, z, h);
    for (int i = 0; i < 30; i++) { CarInput in = {0}; carUpdate(&car, &w, &in, 1 / 60.f); }
    carSetSpeed(&car, kmh / 3.6f); float v0 = kmh / 3.6f, dmin = 1e9f, vmin = 0, vAtMin = 0, maxY = car.y; int firstHit = -1; float hitV = 0, hx = 0, hz = 0, hy = 0; int hn = 0; unsigned char ht[4] = {0}; float hnx[4] = {0}, hnz[4] = {0};
    char idx[200] = ""; int reached = 0;
    for (int fr = 0; fr < secs * 60; fr++) {
      CarInput in = {0}; in.throttle = car.v < v0 ? 1 : 0;
      CarBox pre; carBox(&car, &pre); pre.x += fx * car.v / 60.f * 1.0f; pre.z += fz * car.v / 60.f * 1.0f;
      carUpdate(&car, &w, &in, 1 / 60.f);
      float dd = hypotf(car.x - tx, car.z - tz); if (dd < dmin) { dmin = dd; vAtMin = car.v; }
      if (car.y > maxY) maxY = car.y;
      if (!reached && dd < 4.f && car.v >= .6f * v0) reached = 1;
      if (firstHit < 0 && car.contacts > 0 && car.hitSpeed > 3.f) {
        firstHit = fr; hitV = car.hitSpeed; hx = car.x; hy = car.y; hz = car.z; hn = car.contacts > 4 ? 4 : car.contacts; for (int q = 0; q < hn; q++) { ht[q] = car.ctype[q]; hnx[q] = car.cnx[q]; hnz[q] = car.cnz[q]; }
        float mx, mz, nx, nz; CarBox pb = pre; colPushCar(&w, &pb, &mx, &mz, &nx, &nz); int o = 0;
        for (int q = 0; q < pb.n && o < 180; q++) o += snprintf(idx + o, 200 - o, "%s%d:%u", q ? "," : "", pb.type[q], pb.index[q]);
      }
      if (reached || (firstHit >= 0 && fr > firstHit + 30)) break;
    }
    printf("%s %s dmin %.1f v0 %.1f vAtMin %.1f maxY %.2f", tag, reached && firstHit < 0 ? "PASS" : (reached ? "PASS_HIT" : "FAIL"), dmin, v0, vAtMin, maxY);
    if (firstHit >= 0) { printf(" hit %.1f at %.2f %.2f %.2f frame %d prims %s n", hitV, hx, hy, hz, firstHit, idx); for (int q = 0; q < hn; q++) printf(" %.2f,%.2f(t%d)", hnx[q], hnz[q], ht[q]); }
    printf("\n");
  }
  return 0;
}
