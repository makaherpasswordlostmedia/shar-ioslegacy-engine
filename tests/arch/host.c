// Рой заездов на проём/арку здания уровня (L2 H8-1: здание x 0…25, z −12…30, под ним в COL1 земли нет): машина с разных сторон, скоростей, углов и высот
// (прыжок с подъёма: стартовая высота и вертикальная скорость). Плохой заезд: центр кузова внутри твёрдого ящика (глубина > DEPTH_BAD), или скачок
// позиции за кадр > JUMP_BAD сверх скорости, или остаточное проникновение c.pen > PEN_BAD дольше PEN_FR кадров. Код тот же, что на PSP (viewer/car.c, col.c).
//   host LEVEL.shr [x0 x1 z0 z1]   область здания (по умолчанию L2 H8-1: −12…36, −16…36); печать плохих заездов и итог; код 1 — плохие есть
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "col.h"
#include "car.h"
static ColWorld W; static CarParams P;
#ifndef DEPTH_BAD
#define DEPTH_BAD 0.4f
#endif
#ifndef JUMP_BAD
#define JUMP_BAD 1e9f   /* скачок позиции в полёте от толчка по гравитации мерить нельзя: оставлен справкой */
#endif
#ifndef POP_H
#define POP_H 1.0f
#endif
#ifndef POP_Y
#define POP_Y 1.6f
#endif
#ifndef THIN_MAX
#define THIN_MAX 0.9f      /* ящик с полутолщиной меньше этого — тонкая плита */
#endif
#ifndef PEN_BAD
#define PEN_BAD 0.35f
#endif
#ifndef PEN_FR
#define PEN_FR 20
#endif
static int thin[4096], nthin;   // индексы тонких ящиков (плит) в области
static int thinAxis[4096];
static void findThin(float x0, float x1, float z0, float z1) {
  nthin = 0;
  for (unsigned i = 0; i < W.nbox && nthin < 4096; i++) { const ColBox *B = &W.box[i]; if (B->pad != 0.f) continue;
    int k = B->h[0] < B->h[1] ? (B->h[0] < B->h[2] ? 0 : 2) : (B->h[1] < B->h[2] ? 1 : 2); if (B->h[k] > THIN_MAX) continue;
    if (B->c[0] < x0 - 30.f || B->c[0] > x1 + 30.f || B->c[2] < z0 - 30.f || B->c[2] > z1 + 30.f) continue;
    thin[nthin] = (int)i; thinAxis[nthin++] = k; }
}
static float depthIn(float px, float py, float pz) {   // глубина точки внутри самого глубокого ящика (0 — снаружи)
  float best = 0.f;
  for (unsigned i = 0; i < W.nbox; i++) { const ColBox *B = &W.box[i]; if (B->pad != 0.f) continue;   // листва/фантомы не твёрдые
    float d[3] = {px - B->c[0], py - B->c[1], pz - B->c[2]}, m = 1e9f;
    const float *ax[3] = {B->ax, B->ay, B->az};
    for (int k = 0; k < 3; k++) { float p = fabsf(d[0] * ax[k][0] + d[1] * ax[k][1] + d[2] * ax[k][2]); float in = B->h[k] - p; if (in < m) m = in; }
    if (m > best) best = m; }
  return best;
}
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long sz = ftell(f); rewind(f); unsigned char *d = malloc(sz);
  if (fread(d, 1, sz, f) != (size_t)sz) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96); if (colInit(&W, d + co, ce - co)) return 2;
  carParamsFor("famil_v", &P);
  float bx0 = argc > 5 ? atof(argv[2]) : -12.f, bx1 = argc > 5 ? atof(argv[3]) : 36.f, bz0 = argc > 5 ? atof(argv[4]) : -16.f, bz1 = argc > 5 ? atof(argv[5]) : 36.f;
  findThin(bx0, bx1, bz0, bz1);
  const float vs[] = {8.f, 12.f, 16.f, 20.f, 25.f, 30.f}, ang[] = {-25.f, -12.f, 0.f, 12.f, 25.f}, lift[] = {0.f, 2.f, 4.f}, vy[] = {0.f, 4.f, 8.f};
  if (getenv("ARCH_HITS")) {   // самые резкие удары у арки: ARCH_HITS=N заездов, печать 20 лучших (потеря скорости за кадр) с позицией, курсом, скоростью и номером кадра (60 к/с от старта заезда)
    int N = atoi(getenv("ARCH_HITS")); unsigned rs = 777u; typedef struct { float dv, x, y, z, h, v; int fr; float sx, sy, sz, sh, sv, sup; } Hit; static Hit top[64]; int nt = 0;
#define RND2() (rs ^= rs << 13, rs ^= rs >> 17, rs ^= rs << 5, (rs & 0xffffff) / 16777216.f)
    for (int n = 0; n < N; n++) {
      float sx = -40.f + RND2() * 32.f, sz = -8.f + RND2() * 16.f, g; if (!colGround(&W, sx, sz, 60.f, -30.f, &g, 0)) continue;
      float hd = 1.5708f + (RND2() - .5f) * 1.1f, v = 8.f + RND2() * 24.f, up = RND2() < 0.5f ? RND2() * 6.f : 0.f, vyy = RND2() * 9.f;
      if (depthIn(sx, g + 0.8f, sz) > 0.05f) continue;
      Car c; carInit(&c, &P, &W, sx, g + 0.1f + up, sz, hd); for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
      carSetSpeed(&c, v); if (up > 0.f) c.vel[1] = vyy; float ssx = c.x, ssy = c.y, ssz = c.z; (void)ssy;
      float best = 0.f, bx = 0, by = 0, bz = 0, bh = 0, bv = 0; int bfr = 0;
      for (int fr = 0; fr < 240; fr++) {
        float vb = hypotf(c.vel[0], c.vel[2]); float ox = c.x, oy = c.y, oz = c.z; CarInput in = { .throttle = (c.v < v) ? 1.f : 0.f }; carUpdate(&c, &W, &in, 1 / 60.f);
        float va = hypotf(c.vel[0], c.vel[2]), dv = vb - va; if (c.x > -12.f && c.x < 6.f && c.z > -9.f && c.z < 9.f && dv > best) { best = dv; bx = ox; by = oy; bz = oz; bh = c.h; bv = vb; bfr = fr; }
      }
      if (best > 3.f) { Hit h = { best, bx, by, bz, bh, bv, bfr, sx, g + up, sz, hd, v, up };
        if (nt < 40) top[nt++] = h; else { int mi = 0; for (int k = 1; k < nt; k++) if (top[k].dv < top[mi].dv) mi = k; if (h.dv > top[mi].dv) top[mi] = h; } }
    }
    for (int a = 0; a < nt; a++) for (int b = a + 1; b < nt; b++) if (top[b].dv > top[a].dv) { Hit t = top[a]; top[a] = top[b]; top[b] = t; }
    for (int k = 0; k < nt && k < 20; k++) printf("  удар %2d: потеря скорости %.1f м/с за кадр, из %.1f м/с; позиция (%.2f %.2f %.2f) курс %.2f рад (%.0f°) кадр удара %d (после старта заезда); старт (%.1f %.1f %.1f) курс %.2f рад %.0f м/с подъём %.1f\n",
        k + 1, top[k].dv, top[k].v, top[k].x, top[k].y, top[k].z, top[k].h, top[k].h * 57.2958f, top[k].fr, top[k].sx, top[k].sy, top[k].sz, top[k].sh, top[k].sv, top[k].sup);
    return 0;
  }
  if (getenv("ARCH_ONE")) {   // один заезд по кадрам: ARCH_ONE="x y z курс_° v [вверх]"
    float x, z, y, hdg, v, up = 0.f; sscanf(getenv("ARCH_ONE"), "%f %f %f %f %f %f", &x, &y, &z, &hdg, &v, &up);
    Car c; carInit(&c, &P, &W, x, y, z, hdg * 0.01745f); for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); printf("  settle %d pos %.2f %.2f %.2f pen %.2f\n", k, c.x, c.y, c.z, c.pen); }
    carSetSpeed(&c, v); if (up > 0.f) c.vel[1] = up;
    int NF = getenv("ARCH_FRAMES") ? atoi(getenv("ARCH_FRAMES")) : 60; for (int fr = 0; fr < NF; fr++) { CarInput in = { .throttle = (c.v < v) ? 1.f : 0.f }; float ox = c.x, oz = c.z; carUpdate(&c, &W, &in, 1 / 60.f);
      printf("  f%02d pos %.2f %.2f %.2f dxz %.2f v %.1f pen %.2f ct %d wallV %.1f type %d idx %u rev %d why %d\n", fr, c.x, c.y, c.z, hypotf(c.x - ox, c.z - oz), c.v, c.pen, c.contacts, c.wallV, c.wallV > 0 ? c.wallType : -1, c.wallV > 0 ? c.wallIdx : 0, c.reverts, c.revWhy); }
    return 0;
  }
  if (getenv("ARCH_RANDOM")) {   // случайный рой: положение в области, высота до +14 м над землёй, курс любой, скорость 4…30 м/с, вертикальная скорость −2…10
    int N = atoi(getenv("ARCH_RANDOM")); unsigned rs = getenv("ARCH_SEED") ? (unsigned)atoi(getenv("ARCH_SEED")) : 12345u; int rbad = 0, rin = 0, rthin = 0, rpen = 0, rok = 0, rpop = 0;
#define RND() (rs ^= rs << 13, rs ^= rs >> 17, rs ^= rs << 5, (rs & 0xffffff) / 16777216.f)
    for (int n = 0; n < N; n++) {
      float sx = bx0 - 20.f + RND() * (bx1 - bx0 + 40.f), sz = bz0 - 10.f + RND() * (bz1 - bz0 + 20.f), g;
      if (!colGround(&W, sx, sz, 60.f, -30.f, &g, 0)) continue;
      if (depthIn(sx, g + 0.8f, sz) > 0.05f) continue;   // старт внутри ящика — не заезд
      float hd = RND() * 6.2832f, v = 4.f + RND() * 26.f, up = RND() < 0.6f ? RND() * 14.f : 0.f, vyy = -2.f + RND() * 12.f;
      Car c; carInit(&c, &P, &W, sx, g + 0.1f + up, sz, hd); for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
      carSetSpeed(&c, v); if (up > 0.f) c.vel[1] = vyy;
      int inFr = 0, penRun = 0, penFr = 0, thinFlip = -1, popFr = 0; float maxD = 0.f, popMax = 0.f, popY = 0.f, popX = 0.f, popYY = 0.f, popZ = 0.f, popV = 0.f, postD = -1.f, postAbove = 0.f, postHJ = 0.f; float prevS[4096]; int prevSet[4096]; memset(prevSet, 0, sizeof prevSet);
      for (int fr = 0; fr < 420; fr++) {
        CarInput in = { .throttle = (c.v < v) ? 1.f : 0.f }; float ox = c.x, oy = c.y, oz = c.z, vx = c.vel[0], vy_ = c.vel[1], vz = c.vel[2]; int rec = c.recoveries; carUpdate(&c, &W, &in, 1 / 60.f);
        if (c.recoveries == rec) { float hj = hypotf(c.x - ox - vx / 60.f, c.z - oz - vz / 60.f), yj = c.y - oy - vy_ / 60.f; if (hj > popMax) popMax = hj; if (yj > popY) popY = yj; if ((hj > POP_H || yj > POP_Y) && !popFr) { popX = ox; popYY = oy; popZ = oz; popV = hypotf(vx, vz); postHJ = hj; postD = depthIn(c.x, c.y + 0.7f, c.z); float gg; postAbove = colGround(&W, c.x, c.z, c.y + 3.f, c.y - 40.f, &gg, 0) ? c.y - gg : 99.f; } if (hj > POP_H || yj > POP_Y) popFr++; }
        float dp = depthIn(c.x, c.y + 0.7f, c.z); if (dp > maxD) maxD = dp; if (dp > 0.15f) inFr++;
        if (c.pen > PEN_BAD) { penRun++; if (penRun > penFr) penFr = penRun; } else penRun = 0;
        for (int t = 0; t < nthin && thinFlip < 0; t++) { const ColBox *B = &W.box[thin[t]]; int k = thinAxis[t]; const float *ax[3] = {B->ax, B->ay, B->az};
          float dd[3] = {c.x - B->c[0], c.y + 0.7f - B->c[1], c.z - B->c[2]}, pr[3];
          for (int q = 0; q < 3; q++) pr[q] = dd[0] * ax[q][0] + dd[1] * ax[q][1] + dd[2] * ax[q][2];
          int inpl = 1; for (int q = 0; q < 3; q++) if (q != k && fabsf(pr[q]) > B->h[q] - 0.2f) inpl = 0;
          if (!inpl || fabsf(pr[k]) > 6.f) { prevSet[t] = 0; continue; }
          if (prevSet[t] && prevS[t] * pr[k] < 0.f && fabsf(prevS[t]) < 3.f && fabsf(pr[k]) < 3.f) thinFlip = thin[t];
          prevS[t] = pr[k]; prevSet[t] = 1; }
      }
      int bi = maxD > DEPTH_BAD || inFr > 6, bp = penFr > PEN_FR, bt = thinFlip >= 0, bu = popFr > 0; rok++; rpop += bu;
      if (bi || bp || bt || bu) { rbad++; rin += bi; rpen += bp; rthin += bt;
        if (rbad <= (getenv("ARCH_MAXPRINT") ? atoi(getenv("ARCH_MAXPRINT")) : 25)) printf("  ПЛОХО старт (%.1f %.1f %.1f) курс %.0f° %.0f м/с вверх %.1f/%.1f: внутри ящика до %.2f (%d кадров), pen %d кадров, сквозь тонкий ящик %d, подброс %d кадров (горизонт до %.2f, вверх до %.2f м сверх скорости) ПЕРВЫЙ в (%.1f %.1f %.1f) при %.1f м/с (рывок %.2f, после него: глубина в ящике %.2f, над землёй %.2f), конец (%.1f %.1f %.1f)\n", sx, g + up, sz, hd * 57.3f, v, up, vyy, maxD, inFr, penFr, thinFlip, popFr, popMax, popY, popX, popYY, popZ, popV, postHJ, postD, postAbove, c.x, c.y, c.z); }
    }
    printf("  случайный рой: заездов %d, плохих %d (внутри ящика %d, проникновение %d, сквозь тонкий ящик %d, подброс %d, тонких ящиков %d)\n", rok, rbad, rin, rpen, rthin, rpop, nthin);
    return rbad ? 1 : 0;
  }
  int runs = 0, bad = 0, badInside = 0, badJump = 0, badPen = 0, badThin = 0; float worstD = 0.f;
  for (int side = 0; side < 4; side++) {   // 0 с запада на восток, 1 с востока, 2 с севера (z−), 3 с юга
    for (int li = 0; li < 8; li++) for (int ai = 0; ai < 5; ai++) for (int vi = 0; vi < 6; vi++) for (int hi = 0; hi < 3; hi++) {
      float lat = 4.f + li * ((side < 2 ? bz1 - bz0 : bx1 - bx0) - 8.f) / 7.f;
      float sx, sz, hd = (side == 0 ? 1.5708f : side == 1 ? -1.5708f : side == 2 ? 0.f : 3.1416f) + ang[ai] * 0.01745f;
      if (side == 0) { sx = bx0 - 30.f; sz = bz0 + lat; } else if (side == 1) { sx = bx1 + 30.f; sz = bz0 + lat; }
      else if (side == 2) { sx = bx0 + lat; sz = bz0 - 30.f; } else { sx = bx0 + lat; sz = bz1 + 30.f; }
      float g; if (!colGround(&W, sx, sz, 60.f, -30.f, &g, 0)) continue;
      Car c; carInit(&c, &P, &W, sx, g + lift[hi] * (hi > 0 ? 1.f : 0.f) + 0.1f, sz, hd);
      for (int k = 0; k < 15; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
      carSetSpeed(&c, vs[vi]); if (hi > 0) c.vel[1] = vy[hi];
      int inFr = 0, penFr = 0, penRun = 0, thinFlip = -1; float prevS[4096]; int prevSet[4096]; memset(prevSet, 0, sizeof prevSet); float flipAt[3] = {0, 0, 0}; float maxD = 0.f, jumpMax = 0.f, maxPen = 0.f; int recov0 = c.recoveries;
      float px = c.x, py = c.y, pz = c.z;
      for (int fr = 0; fr < 360; fr++) {
        CarInput in = { .throttle = (c.v < vs[vi]) ? 1.f : 0.f }; float ox = c.x, oy = c.y, oz = c.z, vx = c.vel[0], vz = c.vel[2];
        carUpdate(&c, &W, &in, 1 / 60.f);
        float dx = c.x - ox - vx / 60.f, dz = c.z - oz - vz / 60.f, dy = fabsf(c.y - oy), jm = hypotf(dx, dz); if (dy > 1.5f && jm < dy) jm = dy;
        if (jm > jumpMax) jumpMax = jm;
        float dp = depthIn(c.x, c.y + 0.7f, c.z); if (dp > maxD) maxD = dp; if (dp > 0.15f) inFr++;
        if (c.pen > PEN_BAD) { penRun++; if (penRun > penFr) penFr = penRun; } else penRun = 0; if (c.pen > maxPen) maxPen = c.pen;
        for (int t = 0; t < nthin && thinFlip < 0; t++) { const ColBox *B = &W.box[thin[t]]; int k = thinAxis[t]; const float *ax[3] = {B->ax, B->ay, B->az};
          float dd[3] = {c.x - B->c[0], c.y + 0.7f - B->c[1], c.z - B->c[2]}, pr[3];
          for (int q = 0; q < 3; q++) pr[q] = dd[0] * ax[q][0] + dd[1] * ax[q][1] + dd[2] * ax[q][2];
          int inpl = 1; for (int q = 0; q < 3; q++) if (q != k && fabsf(pr[q]) > B->h[q] - 0.2f) inpl = 0;
          if (!inpl) { prevSet[t] = 0; continue; }
          if (fabsf(pr[k]) > 6.f) { prevSet[t] = 0; continue; }
          if (prevSet[t] && prevS[t] * pr[k] < 0.f && fabsf(prevS[t]) < 3.f && fabsf(pr[k]) < 3.f) { thinFlip = thin[t]; flipAt[0] = c.x; flipAt[1] = c.y; flipAt[2] = c.z; }
          prevS[t] = pr[k]; prevSet[t] = 1; }
        (void)px; (void)py; (void)pz;
      }
      runs++; int bi = maxD > DEPTH_BAD || inFr > 6, bj = jumpMax > JUMP_BAD, bp = penFr > PEN_FR, bt = thinFlip >= 0; badThin += bt;
      if (bi || bj || bp || bt) { bad++; badInside += bi; badJump += bj; badPen += bp; if (maxD > worstD) worstD = maxD;
        if (bad <= (getenv("ARCH_MAXPRINT") ? atoi(getenv("ARCH_MAXPRINT")) : 25)) printf("  ПЛОХО с%s %s, старт (%.1f %.1f %.1f) курс %+.0f° %.0f м/с подъём %.0f вверх %.0f: внутри ящика до %.2f м (%d кадров), скачок %.2f м/кадр, pen до %.2f (%d кадров подряд), конец (%.1f %.1f %.1f) recov %d; сквозь тонкий ящик %d%s\n",
          side == 0 ? "запада" : side == 1 ? "востока" : side == 2 ? "севера" : "юга", "", sx, g, sz, ang[ai], vs[vi], lift[hi], vy[hi], maxD, inFr, jumpMax, maxPen, penFr, c.x, c.y, c.z, c.recoveries - recov0, thinFlip, thinFlip >= 0 ? " (в точке %.1f %.1f %.1f)" : ""); }
    }
  }
  printf("  рой арки: заездов %d, плохих %d (внутри ящика %d, проникновение %d, сквозь тонкий ящик %d, тонких ящиков в области %d), глубже всего %.2f м\n", runs, bad, badInside, badPen, badThin, nthin, worstD);
  return bad ? 1 : 0;
}
