// Гейт аудита 09.10 п. 15/47: сбитая машина трафика, лежащая на боку, не «перескакивает» на полосу.
// Настоящие viewer/traffic.c + car.c + col.c на build/level.shr (COL1) и build/traffic.shr. Мак, CPU.
// PS2: tw_v14_hit20 / tw_v14_hit35 — сбитый минивэн (до удара стоял) 16,5–18 с лежит, где остановился, на полосу не возвращается;
// В112 записана: едущий minivanA после удара50.379km/h стоит13.76s, не возвращается на полосу
// Возврат на полосу убран; авто-подъём car.c не изменён (native90km/h не получен)
//   side    — машину после удара кладут на крышу (крен 180°, поставлено тестом; с бока 90° минивэн порта сам встаёт на колёса за
//             1,1 с): через 1,8 с она всё ещё твёрдое тело и лежит (крен > 45°), а не стоит на полосе
//   upright — настоящая движущаяся машина после сильного удара (№479, PS2 В112): стоит твёрдым телом ~13,8 с (TRF_RAM_STUN), потом возвращается на полосу
//             (было до 11.10: остаётся телом 15 с); красный -DTRF_RAM_OLD=1 — не возвращается
// Красный: -DTRF_REJOIN_OLD=1 -DTRF_UPRIGHT_OLD=1; через1.5s на полосу в любом положении
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"

static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-8s %s  %s\n", n, ok ? "OK  " : "FAIL", d); fails += !ok; }
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static float ground(float x, float z, float top) { float g; return colGround(&world, x, z, top, -1e6f, &g, 0) ? g : 0.f; }
static void step(void) {
  CarInput ci = {0, 0, 0, 1}; carUpdate(&player, &world, &ci, DT);
  float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z - 7}, fw[3] = {0, 0, 1};
  trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
}
// удар машиной игрока в едущую машину трафика у дома Симпсонов (как tests/traffic/host.c, проверка 5); -1 — не вышло
static int ram(void) {
  trafficReset(&T, &world);
  carInit(&player, NULL, &world, 220.f, ground(220.f, 172.f, 50.f), 172.f, 0.f);
  int drv = -1, phys = 0;
  for (int f = 0; f < 90 && drv < 0; f++) { step(); for (int i = 0; i < T.maxCars; i++) if (T.car[i].mode == TRM_DRIVE && T.car[i].v > 3.f) drv = i; }
  if (drv < 0) return -1;
  Car *k = &T.car[drv].car; float h = k->h + 3.14159265f, sx = k->x + sinf(k->h) * 9.f, sz = k->z + cosf(k->h) * 9.f;
  carInit(&player, NULL, &world, sx, k->y + .5f, sz, h); carSetSpeed(&player, 8.f);
  for (int f = 0; f < 60 && !phys; f++) {
    CarInput ci = {0, 0, 0, 0}; carUpdate(&player, &world, &ci, DT);
    float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z}, fw[3] = {sinf(h), 0, cosf(h)};
    trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT); phys = T.car[drv].mode == TRM_PHYS;
  }
  if (!phys) return -1;
  // машину игрока — назад на 12 м и стоять (не толкает, но рядом: трафик не удаляет сбитую)
  carInit(&player, NULL, &world, player.x - sinf(h) * 12.f, player.y + .5f, player.z - cosf(h) * 12.f, h);
  return drv;
}
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *trf = argc > 2 ? argv[2] : "build/traffic.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("no %s\n", lvl); return 2; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("bad level\n"); return 2; }
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f);
  unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 failed\n"); return 2; }
  FILE *g = fopen(trf, "rb"); if (!g) { printf("no %s\n", trf); return 2; }
  fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (!buf || trafficInitMem(&T, buf, tsize, 0)) { printf("traffic failed\n"); return 2; }
  T.maxPeds = 0;
  char d[300];
  for (int side = 1; side >= 0; side--) {
    int i = ram(); if (i < 0) { check(side ? "side" : "upright", 0, "удар не вышел (нет едущей машины / не стала твёрдым телом)"); continue; }
    TrCar *c = &T.car[i]; Car *k = &c->car;
    if (side) {   // на крышу: крен 180° вокруг продольной оси, поднять на 1 м, без скорости (поставлено тестом; с 90° минивэн порта сам
      // валится на колёса за 1,1 с — неваляшка car.c, — поэтому «лежит» проверяется на крыше)
      float cy = cosf(k->h * .5f), sy = sinf(k->h * .5f), cr = cosf(1.5708f), sr = sinf(1.5708f);
      k->q[0] = cy * cr; k->q[1] = sy * sr; k->q[2] = sy * cr; k->q[3] = cy * sr; k->y += 1.f;
      memset(k->vel, 0, sizeof k->vel); memset(k->w, 0, sizeof k->w); k->v = k->vl = 0.f; c->stillT = 0.f;
    }
    float x0 = k->x, z0 = k->z, rollAt = 0.f, jump = 0.f, px = k->x, pz = k->z; int modeAt = -1, back = -1;
    for (int fr = 0; fr < (int)(15.f / DT); fr++) {
      step();
      float dj = hypotf(k->x - px, k->z - pz); if (dj > jump) jump = dj; px = k->x; pz = k->z;
      if (fr == (int)(1.8f / DT)) { modeAt = c->mode; rollAt = acosf(fmaxf(-1.f, fminf(1.f, 1.f - 2.f * (k->q[1] * k->q[1] + k->q[3] * k->q[3])))) * 57.2958f; }   // наклон оси «вверх» кузова от вертикали
      if (back < 0 && c->mode == TRM_DRIVE) back = fr;
    }
    if (side) {
      snprintf(d, sizeof d, "на крыше: через 1,8 с режим %s, наклон кузова %.0f°; на полосу через %.1f с (car.c ставит на колёса через 2 с)",
               modeAt == TRM_PHYS ? "твёрдое тело" : "полоса", rollAt, back >= 0 ? back * DT : -1.f);
      check("side", modeAt == TRM_PHYS && rollAt > 45.f && back<0, d);
    } else {
      snprintf(d, sizeof d, "на колёсах: на полосу через %.1f с, скачок за кадр до %.1f м, от места удара %.1f м", back >= 0 ? back * DT : -1.f, jump, hypotf(k->x - x0, k->z - z0));
      check("upright", back >= 0 && back * DT >= 12.8f && back * DT <= 14.95f && jump < 1.5f, d);   // №479: стоит ≈13,8 с и возвращается (скачок за кадр ≤ 1,5 м)
    }
  }
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
