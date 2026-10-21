// feel — метрики «ощущения» машины на искусственном полигоне (COL1 собирается в памяти): отскок от стены,
// закрутка от удара в угол, удар по касательной, съезд с бордюра (раскачка), «неваляшка», трамплин, разгон и
// максималка, занос в крутом повороте, урон, машина о машину, сравнение машин по .con.
//   feel [--cars famil_v,compacta,schoolbu,garbage]
// Собирается и против старой машины (-DV9, car_v9.c): там печатается только то, что у неё есть.
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>
#include "col.h"
#include "car.h"

#define PI 3.14159265f
#define FPS 60
#define DEG (180.f / PI)
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

// ------------------------------------------------------------------------------------------------ полигон
static ColTri T[4096]; static int nT;
static ColBox B[64]; static int nB;
static ColWorld W;
static void tri(float ax, float ay, float az, float bx, float by, float bz, float cx, float cy, float cz) {
  ColTri *t = &T[nT++]; t->a[0] = ax; t->a[1] = ay; t->a[2] = az; t->b[0] = bx; t->b[1] = by; t->b[2] = bz; t->c[0] = cx; t->c[1] = cy; t->c[2] = cz;
  float ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
  float nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, l = sqrtf(nx * nx + ny * ny + nz * nz);
  t->n[0] = nx / l; t->n[1] = ny / l; t->n[2] = nz / l;
}
// четырёхугольник земли над [x0,x1] x [z0,z1], высоты по z: y0 у z0, y1 у z1 (нормаль вверх)
static void quad(float x0, float x1, float z0, float z1, float y0, float y1) {
  tri(x0, y0, z0, x0, y1, z1, x1, y0, z0);
  tri(x0, y1, z1, x1, y1, z1, x1, y0, z0);
}
static void box(float cx, float cy, float cz, float hx, float hy, float hz) {
  ColBox *b = &B[nB++]; memset(b, 0, sizeof *b);
  b->c[0] = cx; b->c[1] = cy; b->c[2] = cz; b->ax[0] = 1; b->ay[1] = 1; b->az[2] = 1; b->h[0] = hx; b->h[1] = hy; b->h[2] = hz;
}
static void *colBlob;
static void buildWorld(void) {
  // земля: квадраты 50 м на x [-300, 300], z [-300, 1000]
  for (float x = -300; x < 300; x += 50) for (float z = -300; z < 1000; z += 50) quad(x, x + 50, z, z + 50, 0, 0);
  box(0, 2, 301, 40, 2, 1);            // стена: грань z = 300, x -40..40
  box(80, 2, 300.5f, 0.5f, 2, 0.5f);   // столб 1 x 1 м в (80, 300)
  box(-100, 0.15f, 150, 20, 0.15f, 50);   // бордюр-площадка 0.3 м: z 100..200
  quad(140, 160, 100, 112.44f, 0.f, 3.333f);   // трамплин 15 градусов, 12.4 м, высота 3.33 (торец открыт)
  float ox = -300, oz = -300, cell = 4; int Wd = 150, Hd = 325;
  // клетки: у каждого примитива — все клетки его xz-габарита
  int ncell = Wd * Hd; uint32_t *cnt = calloc(ncell + 1, 4);
  #define RANGE(x0, z0, x1, z1) int gx0 = (int)floorf(((x0) - ox) / cell), gz0 = (int)floorf(((z0) - oz) / cell), \
      gx1 = (int)floorf(((x1) - ox) / cell), gz1 = (int)floorf(((z1) - oz) / cell); \
      if (gx0 < 0) gx0 = 0; if (gz0 < 0) gz0 = 0; if (gx1 >= Wd) gx1 = Wd - 1; if (gz1 >= Hd) gz1 = Hd - 1;
  for (int pass = 0; pass < 2; pass++) {
    uint32_t *refs = 0, *fill = 0;
    if (pass == 1) {
      uint32_t acc = 0; for (int i = 0; i < ncell; i++) { uint32_t k = cnt[i]; cnt[i] = acc; acc += k; } cnt[ncell] = acc;
      size_t sz = 48 + nT * 48 + nB * 64 + (ncell + 1) * 4 + acc * 4 + 16;
      colBlob = calloc(1, sz); char *p = colBlob;
      memcpy(p, "COL1", 4); float *hf = (float *)(p + 4); hf[0] = ox; hf[1] = oz; hf[2] = cell;
      uint32_t *hu = (uint32_t *)(p + 16); hu[0] = Wd; hu[1] = Hd; hu[2] = nT; hu[3] = nB; hu[4] = 0; hu[5] = 0; hu[6] = acc; hu[7] = 0;
      memcpy(p + 48, T, nT * 48); memcpy(p + 48 + nT * 48, B, nB * 64);
      uint32_t *cs = (uint32_t *)(p + 48 + nT * 48 + nB * 64); memcpy(cs, cnt, (ncell + 1) * 4);
      refs = cs + ncell + 1; fill = calloc(ncell, 4); memcpy(fill, cnt, ncell * 4);
    }
    for (int i = 0; i < nT; i++) {
      ColTri *t = &T[i];
      float x0 = fminf(t->a[0], fminf(t->b[0], t->c[0])), x1 = fmaxf(t->a[0], fmaxf(t->b[0], t->c[0]));
      float z0 = fminf(t->a[2], fminf(t->b[2], t->c[2])), z1 = fmaxf(t->a[2], fmaxf(t->b[2], t->c[2]));
      RANGE(x0, z0, x1, z1)
      for (int gz = gz0; gz <= gz1; gz++) for (int gx = gx0; gx <= gx1; gx++) { int c = gz * Wd + gx; if (pass) refs[fill[c]++] = (0u << 29) | i; else cnt[c]++; }
    }
    for (int i = 0; i < nB; i++) {
      ColBox *b = &B[i];
      RANGE(b->c[0] - b->h[0], b->c[2] - b->h[2], b->c[0] + b->h[0], b->c[2] + b->h[2])
      for (int gz = gz0; gz <= gz1; gz++) for (int gx = gx0; gx <= gx1; gx++) { int c = gz * Wd + gx; if (pass) refs[fill[c]++] = (1u << 29) | i; else cnt[c]++; }
    }
    if (pass) free(fill);
  }
  uint32_t *hu = (uint32_t *)((char *)colBlob + 16);
  size_t sz = 48 + nT * 48 + nB * 64 + (ncell + 1) * 4 + hu[6] * 4;
  int r = colInit(&W, colBlob, (unsigned)sz);
  if (r) { fprintf(stderr, "colInit: %s\n", colError(r)); exit(1); }
  free(cnt);
}

// ------------------------------------------------------------------------------------------------ машина
static const char *carName = "famil_v";
static double cpuSum; static long cpuN;
static void place(Car *c, float x, float z, float h) {
#ifdef V9
  carInit(c, 0, &W, x, 0.f, z, h);
#else
  CarParams p; carParamsFor(carName, &p); carInit(c, &p, &W, x, 0.f, z, h);
#endif
}
static void setSpeed(Car *c, float v) {
#ifdef V9
  c->v = v;
#else
  carSetSpeed(c, v);
#endif
}
static void step(Car *c, float thr, float brk, float steer, int hb) {
  CarInput in; memset(&in, 0, sizeof in); in.throttle = thr; in.brake = brk; in.steer = steer;
#ifndef V9
  in.handbrake = (float)hb;
#else
  (void)hb;
#endif
  double t0 = now(); carUpdate(c, &W, &in, 1.f / FPS); cpuSum += now() - t0; cpuN++;
}
static float upY(const Car *c) {
#ifdef V9
  return cosf(c->pitch) * cosf(c->roll);
#else
  float x = c->q[1], z = c->q[3]; return 1 - 2 * (x * x + z * z);
#endif
}
static float dmg(const Car *c) {
#ifdef V9
  (void)c; return 0.f;
#else
  return c->damage;
#endif
}
static int traceOn;
#ifdef COL_DEBUG
extern int colDebug;
#endif
static void trace(const char *tag, int f, const Car *c) {
  if (!traceOn) return;
#ifdef V9
  printf("%s f%3d x %7.2f y %6.3f z %7.2f h %+6.3f v %6.2f vl %+5.2f vy %+6.2f pitch %+5.1f roll %+5.1f gr %d wh %d hit %.1f\n", tag, f, c->x, c->y, c->z, c->h, c->v, c->vl, c->vy, c->pitch * DEG, c->roll * DEG, c->grounded, c->wheels, c->hitSpeed);
#else
  printf("%s f%3d x %7.2f y %6.3f z %7.2f h %+6.3f v %6.2f vl %+5.2f vy %+6.2f pitch %+5.1f roll %+5.1f gr %d wh %d comp %.2f %.2f %.2f %.2f hit %.1f w %+.2f %+.2f %+.2f\n", tag, f, c->x, c->y, c->z, c->h, c->v, c->vl, c->vy, c->pitch * DEG, c->roll * DEG, c->grounded, c->wheels,
         c->comp[0], c->comp[1], c->comp[2], c->comp[3], c->hitSpeed, c->w[0], c->w[1], c->w[2]);
#endif
}
static float wrapPi(float a) { while (a > PI) a -= 2 * PI; while (a < -PI) a += 2 * PI; return a; }

// ------------------------------------------------------------------------------------------------ тесты
typedef struct { float vBefore, rebound, e, hop, pitchMax, dmg, yaw, dh, keep, up; } Hit;
// лобовой удар в стену z = 300: разгон не нужен — ставим в 4 м перед стеной с заданной скоростью, без газа
static Hit wallHit(float kmh, float angDeg, float xOfs, int pillar) {
  Car c; float a = angDeg / DEG, v0 = kmh / 3.6f;
  float x = (pillar ? 80.f : 0.f) + xOfs, zf = 300.f - 5.5f;   // нос в ~3 м от стены
  place(&c, x - sinf(a) * 2.f, zf - cosf(a) * 2.f, a); setSpeed(&c, v0);
  Hit H; memset(&H, 0, sizeof H);
  float y0 = c.y, d0 = dmg(&c), h0 = c.h, vPrev = c.v; int hitF = -1; float hPrev = c.h, yawMax = 0;
  for (int f = 0; f < 3 * FPS; f++) {
#ifdef COL_DEBUG
    colDebug = traceOn == 2 && f >= 14 && f <= 26;
#endif
    step(&c, hitF < 0 && c.v < v0 ? 1.f : 0.f, 0, 0, 0); if (f < 90) trace("hit", f, &c);
    if (hitF < 0 && c.hitSpeed > 0.5f) { hitF = f; H.vBefore = vPrev; }
    if (hitF >= 0 && f - hitF < FPS / 3 && -c.v > H.rebound) H.rebound = -c.v;   // скорость назад вдоль носа
    if (hitF >= 0 && f - hitF < FPS) {
      if (c.y - y0 > H.hop) H.hop = c.y - y0;
      if (fabsf(c.pitch) > H.pitchMax) H.pitchMax = fabsf(c.pitch);
      float yr = fabsf(wrapPi(c.h - hPrev)) * FPS; if (yr > yawMax) yawMax = yr;
    }
    if (hitF >= 0 && f - hitF == FPS / 2) { H.dh = wrapPi(c.h - h0); H.keep = sqrtf(c.v * c.v + c.vl * c.vl) / fmaxf(0.1f, H.vBefore); }
    vPrev = c.v; hPrev = c.h;
  }
  H.e = H.vBefore > 0 ? H.rebound / H.vBefore : 0; H.dmg = dmg(&c) - d0; H.yaw = yawMax; H.up = upY(&c);
  return H;
}

typedef struct { float settle, wob, pitchMax, vyMax, bottom; } Drop;
// съезд с бордюра 0.3 м (площадка кончается на z = 200) на 36 км/ч накатом
static Drop curbDrop(void) {
  Car c; place(&c, -100.f, 188.f, 0.f); setSpeed(&c, 10.f); int held = 1;
  Drop D; memset(&D, 0, sizeof D);
  int t0 = -1, last = 0; float pPrev = 0, dpPrev = 0; int cross = 0;
  for (int f = 0; f < 5 * FPS; f++) {
    if (c.z > 200.f - 3.f) held = 0;   // до края держим 36 км/ч, дальше накат
    step(&c, held && c.v < 10.f ? 1.f : 0.f, 0, 0, 0);
    if (t0 < 0 && c.z > 200.f + c.p.wheelR + 0.3f) t0 = f;
    if (t0 >= 0) {
      if (fabsf(c.pitch) > D.pitchMax) D.pitchMax = fabsf(c.pitch);
      if (fabsf(c.pitch) > 0.5f / DEG || fabsf(c.roll) > 0.5f / DEG || fabsf(c.vy) > 0.1f) last = f;
      float dp = c.pitch - pPrev;
      if (f > t0 + 1 && dp * dpPrev < 0 && fabsf(c.pitch) > 0.3f / DEG) cross++;
      dpPrev = dp;
    }
    pPrev = c.pitch;
  }
  D.settle = t0 >= 0 ? (last - t0) / (float)FPS : -1; D.wob = cross * 0.5f;
  return D;
}

typedef struct { float settle, over, wob; } Wob;
#ifndef V9
// «неваляшка»: машину на ровном ставим с креном 35 градусов (правый борт вверх) и отпускаем
static Wob weebleTest(float degs) {
  Car c; place(&c, -200.f, 600.f, 0.f);
  float a = degs / DEG, s = sinf(a * .5f), co = cosf(a * .5f);
  // крен вокруг оси вперёд (z тела): правый борт вверх = поворот вокруг +z на -a (x тела — влево)
  float q[4] = {co, 0, 0, -s}, *p = c.q; float r0 = p[0], r1 = p[1], r2 = p[2], r3 = p[3];   // q_yaw * q_roll
  p[0] = r0 * q[0] - r1 * q[1] - r2 * q[2] - r3 * q[3]; p[1] = r0 * q[1] + r1 * q[0] + r2 * q[3] - r3 * q[2];
  p[2] = r0 * q[2] - r1 * q[3] + r2 * q[0] + r3 * q[1]; p[3] = r0 * q[3] + r1 * q[2] - r2 * q[1] + r3 * q[0];
  c.y += sinf(a) * c.p.wheelX + 0.05f;   // левые колёса на земле
  Wob R; memset(&R, 0, sizeof R); int last = 0, cross = 0; float rPrev = 0;
  for (int f = 0; f < 6 * FPS; f++) {
    step(&c, 0, 0, 0, 0);
    if (fabsf(c.roll) > 1.f / DEG) last = f;
    if (fabsf(c.roll) > 0.5f / DEG) { if (c.roll * rPrev < 0) cross++; rPrev = c.roll; }
    if (c.roll < 0 && -c.roll > R.over) R.over = -c.roll;
  }
  R.settle = last / (float)FPS; R.wob = (float)cross; R.over *= DEG;
  return R;
}
#endif

typedef struct { float air, height, pitchOff, pitchLand, pitchMax, up, settle, bottom, dist; int flip; } Jump;
// трамплин 15 градусов на 90 км/ч с газом
static Jump ramp(float kmh) {
  Car c; place(&c, 150.f, 60.f, 0.f); setSpeed(&c, kmh / 3.6f);
  Jump J; memset(&J, 0, sizeof J); J.up = 1;
  int off = -1, land = -1, last = 0, airF = 0; float top = 3.333f;
  for (int f = 0; f < 8 * FPS; f++) {
    float v = kmh / 3.6f; step(&c, c.v < v ? 1.f : 0.f, 0, 0, 0); if (f < 400) trace("ramp", f, &c);
    // оторвался: задняя ось за краем трамплина; приземлился: первое касание после этого
    if (off < 0 && c.z - c.p.wheelR > 112.44f) { off = f; J.pitchOff = c.pitch * DEG; }
    if (off >= 0 && land < 0) {
      if (!c.grounded) airF++;
      if (c.y - top > J.height) J.height = c.y - top;
      if (c.grounded && airF > 3) { land = f; J.pitchLand = c.pitch * DEG; J.dist = c.z - 112.44f; }
    }
    if (land >= 0 && f < land + 2 * FPS) {
      if (fabsf(c.pitch) * DEG > J.pitchMax) J.pitchMax = fabsf(c.pitch) * DEG;
      float u = upY(&c); if (u < J.up) J.up = u;
      if (fabsf(c.pitch) > 1.f / DEG || fabsf(c.roll) > 1.f / DEG || fabsf(c.vy) > 0.2f) last = f;
#ifndef V9
      if (!c.wheels && c.grounded) J.bottom += 1.f / FPS;
#endif
    }
  }
  J.air = airF / (float)FPS; J.settle = land >= 0 ? (last - land) / (float)FPS : -1;
#ifndef V9
  J.flip = c.rights;
#endif
  return J;
}

typedef struct { float top, t100, dist100; } Accel;
static Accel accel(void) {
  Car c; place(&c, -250.f, -250.f, 0.f);
  Accel A; A.t100 = -1; A.dist100 = 0; float z0 = c.z;
  for (int f = 0; f < 25 * FPS; f++) {
    step(&c, 1, 0, 0, 0);
    if (A.t100 < 0 && c.v >= 100.f / 3.6f) { A.t100 = (f + 1) / (float)FPS; A.dist100 = c.z - z0; }
  }
  A.top = c.v * 3.6f;
  return A;
}

typedef struct { float yaw, latG, slip, slipMax, vEnd, radius, dh15; } Turn;
// крутой поворот: разгон до скорости, затем полный руль вправо на 3 с (газ / накат / ручник)
static Turn turn(float kmh, float thr, int hb) {
  Car c; place(&c, 200.f, 400.f, 0.f); setSpeed(&c, kmh / 3.6f);
  Turn R; memset(&R, 0, sizeof R);
  float hPrev = c.h; double yawS = 0, latS = 0, slipS = 0; int n = 0;
  for (int f = 0; f < 3 * FPS; f++) {
    step(&c, thr, 0, 1.f, hb && f < FPS);
    float vx = c.v, vl = c.vl, sp = sqrtf(vx * vx + vl * vl), yr = wrapPi(c.h - hPrev) * FPS; hPrev = c.h;
    float slip = sp > 1.f ? atan2f(fabsf(vl), fabsf(vx)) * DEG : 0.f;
    if (slip > R.slipMax) R.slipMax = slip;
    R.dh15 += f < FPS * 3 / 2 ? fabsf(yr) / FPS * DEG : 0.f;
    if (f >= FPS) { yawS += fabsf(yr); latS += fabsf(yr) * sp; slipS += slip; n++; }
  }
  R.yaw = (float)(yawS / n) * DEG; R.latG = (float)(latS / n) / 9.81f; R.slip = (float)(slipS / n); R.vEnd = sqrtf(c.v * c.v + c.vl * c.vl) * 3.6f;
  R.radius = R.yaw > 0.1f ? (R.vEnd / 3.6f) / (R.yaw / DEG) : 0;
  return R;
}

// тормоз с 100 км/ч до нуля (путь), стоянка на трамплине 15 градусов без газа (сползание за 5 с), задний ход
static void misc(void) {
  Car c; place(&c, -250.f, -250.f, 0.f); setSpeed(&c, 100.f / 3.6f); float z0 = c.z; int f = 0;
  for (; f < 10 * FPS && c.v > 0.3f; f++) step(&c, 0, 1, 0, 0);
  float stopD = c.z - z0, stopT = f / (float)FPS;
  place(&c, 150.f, 105.f, 0.f); float x0 = c.x, zz0 = c.z, y0 = c.y;
  for (f = 0; f < 5 * FPS; f++) step(&c, 0, 0, 0, 0);
  float creep = sqrtf((c.x - x0) * (c.x - x0) + (c.z - zz0) * (c.z - zz0));
  place(&c, -250.f, 300.f, 0.f);
  for (f = 0; f < 6 * FPS; f++) step(&c, 0, 1, 0, 0);
  printf("brake from 100 km/h: %.1f m, %.2f s | parked on the 15 deg ramp (y %.2f), no input: slid %.3f m in 5 s | reverse (6 s full brake from rest): %.0f km/h\n",
         stopD, stopT, y0, creep, c.v * 3.6f);
}
#ifndef V9
// перевёрнутая машина: кладём на крышу и ждём (через 2 с её ставят на колёса)
static void flipTest(void) {
  Car c; place(&c, -200.f, 700.f, 0.f);
  float *p = c.q, r0 = p[0], r1 = p[1], r2 = p[2], r3 = p[3], q[4] = {0.f, 0.f, 0.f, 1.f};   // 180 градусов вокруг z
  p[0] = r0 * q[0] - r1 * q[1] - r2 * q[2] - r3 * q[3]; p[1] = r0 * q[1] + r1 * q[0] + r2 * q[3] - r3 * q[2];
  p[2] = r0 * q[2] - r1 * q[3] + r2 * q[0] + r3 * q[1]; p[3] = r0 * q[3] + r1 * q[2] - r2 * q[1] + r3 * q[0];
  c.y += c.p.bodyHi + 0.2f;
  int f = 0, rg = c.rights;
  for (; f < 6 * FPS && c.rights == rg; f++) step(&c, 0, 0, 0, 0);
  float t = f / (float)FPS; for (int k = 0; k < FPS; k++) step(&c, 0, 0, 0, 0);
  printf("upside down on flat ground: put back on its wheels after %.2f s (up.y then %.2f, wheels %d, recoveries %d)\n", t, upY(&c), c.wheels, c.recoveries);
}
typedef struct { float va, vb, dva, dvb, da, db; } Crash;
// машина о машину: лоб в лоб по 40 км/ч (своя — carName, встречная — other)
static Crash crash(const char *other) {
  Car a, b; CarParams pa, pb; carParamsFor(carName, &pa); carParamsFor(other, &pb);
  carInit(&a, &pa, &W, -150.f, 0, 590.f, 0.f); carInit(&b, &pb, &W, -150.3f, 0, 600.f, PI);
  carSetSpeed(&a, 11.1f); carSetSpeed(&b, 11.1f);
  Crash C; memset(&C, 0, sizeof C);
  for (int f = 0; f < 2 * FPS; f++) {
    step(&a, 0, 0, 0, 0); step(&b, 0, 0, 0, 0);
    carHitCar(&a, &b, &W);
    if (f == FPS / 2) { C.va = a.v * 3.6f; C.vb = b.v * 3.6f; }
  }
  C.dva = 40.f + C.va; C.dvb = 40.f + C.vb; C.da = a.damage; C.db = b.damage;
  return C;
}
#endif

// ------------------------------------------------------------------------------------------------ отчёт
#ifdef V9
static const char *MODEL = "v9 (arcade, car_v9.c)";
#else
static const char *MODEL = "v10 (rigid body)";
#endif
static void report(int full) {
  printf("=== %s, car %s ===\n", MODEL, carName);
  printf("wall hits (coast into a wall, nose ~3 m away):\n");
  printf("  head-on   km/h  v_before  rebound  e=after/before  hop(m)  max pitch  damage   up-after\n");
  float sp[3] = {30, 60, 100};
  for (int i = 0; i < 3; i++) {
    Hit H = wallHit(sp[i], 0, 0, 0);
    printf("            %4.0f  %6.1f   %6.1f   %6.2f          %5.2f   %6.1f     %5.3f    %5.2f\n", sp[i], H.vBefore * 3.6f, H.rebound * 3.6f, H.e, H.hop, H.pitchMax * DEG, H.dmg, H.up);
  }
  { Hit H = wallHit(60, 0, 1.2f, 1);
    printf("  off-centre 60 km/h, pillar under the right headlight: peak yaw %.0f deg/s, heading change after 0.5 s %.0f deg, rebound e %.2f\n", H.yaw * DEG, H.dh * DEG, H.e); }
  { Hit H = wallHit(60, 60, 0, 0);
    printf("  glancing (30 deg to the wall), 60 km/h: speed kept after 0.5 s %.0f%%, heading change %.0f deg (toward wall-parallel = +), peak yaw %.0f deg/s\n", H.keep * 100, H.dh * DEG, H.yaw * DEG); }
  Drop D = curbDrop();
  printf("curb drop 0.3 m at 36 km/h (coasting): max pitch %.1f deg, pitch wobbles %.1f, settled (<0.5 deg, |vy|<0.1) after %.2f s\n", D.pitchMax * DEG, D.wob, D.settle);
#ifndef V9
  { Wob R = weebleTest(35); printf("weeble: released at 35 deg roll: back on 4 wheels, roll sign changes %.0f, overshoot %.1f deg, settled (<1 deg) after %.2f s\n", R.wob, R.over, R.settle); }
  { Wob R = weebleTest(70); printf("weeble: released at 70 deg roll (on two wheels, almost on its side): roll sign changes %.0f, overshoot %.1f deg, settled after %.2f s\n", R.wob, R.over, R.settle); }
#endif
  float rk[2] = {60, 90};
  for (int i = 0; i < 2; i++) {
    Jump J = ramp(rk[i]);
    printf("ramp 15 deg / 3.3 m at %.0f km/h: airtime %.2f s, apex %.2f m above ramp top, jump length %.1f m, pitch at take-off %+.0f, at landing %+.0f, max after %.0f deg, min up.y %.2f, on belly %.2f s, settled after %.2f s, flips %d\n",
           rk[i], J.air, J.height, J.dist, J.pitchOff, J.pitchLand, J.pitchMax, J.up, J.bottom, J.settle, J.flip);
  }
  misc();
#ifndef V9
  flipTest();
#endif
  Accel A = accel();
  printf("full throttle on flat: 0-100 km/h %.2f s (%.0f m), speed after 25 s %.1f km/h\n", A.t100, A.dist100, A.top);
  float tk[2] = {50, 90};
  for (int i = 0; i < 2; i++) {
    Turn G = turn(tk[i], 1.f, 0), K = turn(tk[i], 0.f, 0);
    printf("full right lock at %.0f km/h, gas: yaw %.0f deg/s, lateral %.2f g, slide angle avg %.1f / max %.1f deg, radius %.0f m, end %.0f km/h | coasting: yaw %.0f, %.2f g, slide %.1f / %.1f deg, end %.0f km/h\n",
           tk[i], G.yaw, G.latG, G.slip, G.slipMax, G.radius, G.vEnd, K.yaw, K.latG, K.slip, K.slipMax, K.vEnd);
  }
#ifndef V9
  { Turn H = turn(70, 1.f, 1), G = turn(70, 1.f, 0);
    printf("handbrake turn at 70 km/h (1 s handbrake + full lock + gas): turned %.0f deg in 1.5 s (without handbrake %.0f), slide max %.1f deg (without %.1f), end %.0f km/h\n", H.dh15, G.dh15, H.slipMax, G.slipMax, H.vEnd); }
  if (full) {
    const char *o[3] = {"compacta", "famil_v", "schoolbu"};
    for (int i = 0; i < 3; i++) { Crash C = crash(o[i]); printf("head-on vs %-9s 40+40 km/h: after 0.5 s %s %.0f km/h, %s %.0f km/h (speed change %.0f / %.0f), damage %.2f / %.2f\n",
                                                          o[i], carName, C.va, o[i], C.vb, C.dva, C.dvb, C.da, C.db); }
  }
#endif
  (void)full;
}

// предсказание модели hit-and-run-web (vehicle-physics.ts) с теми же .con: 0-100 = V/(2 Gas) * atanh(27.8/V),
// максималка = TopSpeed (равновесие), отскок от стены 0.12, предел поворота TireGrip g
#ifndef V9
static void hrw(void) {
  CarParams p; carParamsFor(carName, &p);
  float V = p.topSpeed, a = 2.f * p.gasScale, t = V > 27.78f ? V / a * atanhf(27.78f / V) : -1;
  printf("hit-and-run-web model with %s .con: 0-100 %.2f s, top %.0f km/h, wall restitution 0.12 (> 1 m/s), lateral limit %.2f g, damage (v-2)*0.85/100/(HP/3) per hit (HP %.1f)\n",
         carName, t, V * 3.6f, p.tireGrip, p.hitPoints);
}
#endif

int main(int argc, char **argv) {
  const char *cars = 0;
  const char *only = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--cars") && i + 1 < argc) cars = argv[++i];
    else if (!strcmp(argv[i], "--trace") && i + 1 < argc) { traceOn = 1; only = argv[++i]; }
  }
  if (only) {
    buildWorld();
    if (!strcmp(only, "ramp90")) ramp(90); else if (!strcmp(only, "ramp60")) ramp(60);
    else if (!strcmp(only, "wall60")) { traceOn = 2; wallHit(60, 0, 0, 0); }
    else if (!strcmp(only, "wall100c")) { traceOn = 2; carName = "compacta"; wallHit(100, 0, 0, 0); }
    else if (!strcmp(only, "pillarbus")) { traceOn = 2; carName = "schoolbu"; wallHit(60, 0, 1.2f, 1); } else if (!strcmp(only, "pillar")) { traceOn = 2; wallHit(60, 0, 1.2f, 1); }
    return 0;
  }
  buildWorld(); (void)cars;
  report(1);
#ifndef V9
  hrw();
  if (cars) {
    char buf[256]; strncpy(buf, cars, sizeof buf - 1); buf[sizeof buf - 1] = 0;
    printf("\n=== car comparison (same body, .con from the disc) ===\n");
    printf("  car        mass  e(60)  hop(100)  pillar yaw  0-100   top   lat g(90,gas)  slide(90)  curb settle  dmg(60)  hp\n");
    for (char *s = strtok(buf, ","); s; s = strtok(0, ",")) {
      carName = s; CarParams p; carParamsFor(s, &p);
      Hit H60 = wallHit(60, 0, 0, 0), H100 = wallHit(100, 0, 0, 0), P = wallHit(60, 0, 1.2f, 1);
      Accel A = accel(); Turn G = turn(90, 1.f, 0); Drop D = curbDrop();
      printf("  %-9s %5.0f  %5.2f  %6.2f    %6.0f     %5.2f  %5.0f   %5.2f        %5.1f       %5.2f       %5.3f  %4.1f\n",
             s, p.mass, H60.e, H100.hop, P.yaw * DEG, A.t100, A.top, G.latG, G.slip, D.settle, H60.dmg, p.hitPoints);
    }
    carName = "famil_v";
  }
#endif
  printf("cpu per carUpdate (1/60 s, Mac): %.2f us avg over %ld updates\n", cpuSum / cpuN * 1e6, cpuN);
  return 0;
}
