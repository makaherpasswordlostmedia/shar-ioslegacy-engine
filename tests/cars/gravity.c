// Гейт гравитации машины (аудит 09.10 п. 34): число держит поведение, а не строка в коде.
// PS2: build/ps2ref/answers/v1_gravity/trace.tsv (В1, knowledge/facts/ps2-car-gravity.yaml) — машину подняли на 15 м, car_vel[1]
// по кадрам PAL 50 Гц; g PS2 = МНК-наклон скорости в свободном падении (считается здесь из записи, не вписан руками).
// Порт: настоящий viewer/car.c (famil_v по умолчанию, carInit) на коллизии build/level.shr у старта уровня 1 (220, 172), подъём
// на 15 м над землёй, carUpdate шагом 1/60 с; g порта = МНК-наклон vel[1] в полёте. Проверка: |g порта − g PS2| ≤ 0,25 м/с²
// (разброс подгонки PS2 16,0–16,2 из карточки). Красный (tests/cars/gravity.sh): -DGRAV_RED=15 — прежнее число порта (карточка: 15)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "col.h"

static ColWorld world;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static double slope(const double *t, const double *v, int n) {   // МНК v = a + g t
  double st = 0, sv = 0, stt = 0, stv = 0; for (int i = 0; i < n; i++) { st += t[i]; sv += v[i]; stt += t[i] * t[i]; stv += t[i] * v[i]; }
  return (n * stv - st * sv) / (n * stt - st * st);
}
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *trace = argc > 2 ? argv[2] : "build/ps2ref/answers/v1_gravity/trace.tsv";
  // 1) PS2: свободное падение — от первого отсчёта после подъёма (скорость < −0,5) до последнего перед касанием (скорость ещё падает)
  FILE *f = fopen(trace, "r"); if (!f) { printf("FAIL нет записи PS2 %s\n", trace); return 2; }
  static double T[4096], V[4096]; int n = 0; char line[512]; double prevV = 0; int falling = 0;
  if (!fgets(line, sizeof line, f)) return 2;
  while (fgets(line, sizeof line, f) && n < 4096) {
    double tm, rel, fr, cm, vy, my; if (sscanf(line, "%lf %lf %lf %lf %lf %lf", &tm, &rel, &fr, &cm, &vy, &my) != 6) continue;
    if (!falling && vy < -0.5 && cm > 10.0) falling = 1;
    if (falling) { if (vy > prevV || cm < 5.0) break; T[n] = fr / 50.0; V[n] = vy; n++; }
    prevV = vy;
  }
  fclose(f);
  if (n < 8) { printf("FAIL мало отсчётов падения PS2: %d\n", n); return 2; }
  double gps2 = -slope(T, V, n);
  // 2) порт
  f = fopen(lvl, "rb"); if (!f) { printf("no %s\n", lvl); return 2; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("bad level\n"); return 2; }
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f);
  unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 failed\n"); return 2; }
  float g0; if (!colGround(&world, 220.f, 172.f, 50.f, -1e6f, &g0, 0)) g0 = 4.f;
  Car c; carInit(&c, NULL, &world, 220.f, g0 + 15.f, 172.f, 0.f);
  c.y = g0 + 15.f; c.grounded = 0; c.wheels = 0; c.fallTop = c.y;   // carPlace ставит на землю — поднимаем, как запись PS2 (+15 м)
#ifdef GRAV_RED
  c.p.gravity = GRAV_RED;   // красный контроль: прежнее число порта
#endif
  static double t2[2048], v2[2048]; int m = 0; const float dt = 1.f / 60.f; float y0 = c.y;
  for (int k = 0; k < 240 && m < 2048; k++) {
    CarInput in = {0, 0, 0, 0}; carUpdate(&c, &world, &in, dt);
    if (c.grounded || c.y < g0 + 1.f) break;
    if (k >= 2) { t2[m] = k * dt; v2[m] = c.vel[1]; m++; }
  }
  if (m < 8) { printf("FAIL порт: мало кадров полёта %d (y0 %.1f)\n", m, y0); return 1; }
  double gport = -slope(t2, v2, m);
  printf("PS2 v1_gravity: %d отсчётов падения, g = %.2f м/с²; порт (famil_v, c.p.gravity %.1f): %d кадров полёта, g = %.2f м/с²\n",
         n, gps2, c.p.gravity, m, gport);
  int ok = fabs(gport - gps2) <= 0.25 && gps2 > 15.5 && gps2 < 16.5;
  printf("CHECK gravity %s  |g порта − g PS2| = %.2f (допуск 0,25)\n", ok ? "OK  " : "FAIL", fabs(gport - gps2));
  printf("RESULT %s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
