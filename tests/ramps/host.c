unsigned homerSolidFrame;
// Трамплины со стеклом Krusty на реальных данных уровня, тот же кадр, что viewer/main.c (carUpdate -> propsUpdate ->
// spUpdate). Жалоба Роба 27.09: у трамплина со стеклом у дома «нельзя проехать, всё как блок».
// Для каждого из 13 стёкол (PRP1, обломок 19): разгон по линии прыжка (нормаль стекла) с 30/40/50 м, 60–120 км/ч,
// курс −10°/0/+10°. Считаем «щель-стену»: откат подшага «край мира» (revWhy 16), когда под центром нет земли, а по обе
// стороны в пределах 1 м она есть (щель между кусками коллизии, а не край). Таких должно быть 0.
// Контроль: настоящий край мира (земли нет дальше на 8 м) по-прежнему держит машину в полёте.
//   tests/ramps/host.sh [level.shr]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"

static Props props; static StateProps sp; static ColWorld world; static Car car;
static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }
static int onKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz;
  int b = spBreakOf(&sp, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sp, (unsigned)b, pos, props.def[i].q);
}
static int ground(float x, float z, float top) { float g; return colGround(&world, x, z, top, -1e6f, &g, 0); }
// щель: в центре земли нет, а с обеих сторон (вдоль хода или поперёк) в пределах 1 м есть
static int crack(float x, float z, float fx, float fz, float top) {
  if (ground(x, z, top)) return 0;
  for (int k = 0; k < 2; k++) {
    float ax = k ? -fz : fx, az = k ? fx : fz;
    if (ground(x + ax, z + az, top + .3f) && ground(x - ax, z - az, top + .3f)) return 1;
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
  if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) ||
      spInit(&sp, props.spr, props.sprSize)) return 2;
  props.onKick = onKick;
  PropState *st0 = malloc(sizeof(PropState) * props.ninst); memcpy(st0, props.st, sizeof(PropState) * props.ninst);
  const float dt = 1 / 60.f;
  int glass = 0, runs = 0, crackWalls = 0, passed = 0, started = 0;
  for (unsigned i = 0; i < props.ninst; i++) {
    int pa, br; propsTypeFx(&props, props.def[i].type, &pa, &br); if (br != 19) continue;
    glass++;
    const PropState *g0 = &st0[i];
    float qx = g0->q[1], qy = g0->q[2], qz = g0->q[3], qw = g0->q[0];
    float nx = 2 * (qx * qz + qw * qy), nz = 1 - 2 * (qx * qx + qy * qy), len = hypotf(nx, nz); nx /= len; nz /= len;
    int gRuns = 0, gCrack = 0, gPass = 0;
    for (int di = 0; di < 3; di++) {
      float d = 30.f + 10.f * di, sx = g0->x - nx * d, sz = g0->z - nz * d, gy;
      if (!colGround(&world, sx, sz, g0->y + 4.f, g0->y - 12.f, &gy, 0)) continue;   // старт на опоре около высоты трамплина
      for (int vi = 0; vi < 4; vi++) for (int ai = -1; ai <= 1; ai++) {
        memcpy(props.st, st0, sizeof(PropState) * props.ninst); props.havePreviousCar = 0;
        spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) return 2;
        float h = atan2f(nx, nz) + ai * 0.1745f, kmh = 60.f + 20.f * vi;
        carInit(&car, NULL, &world, sx, gy, sz, h);
        for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&car, &world, &in, dt); }
        carSetSpeed(&car, kmh / 3.6f); started++;
        int cw = 0, pass = 0;
        for (int fr = 0; fr < 6 * 60; fr++) {
          CarInput in = {0}; in.throttle = car.v * 3.6f < kmh ? 1.f : 0.f;
          float x0 = car.x, z0 = car.z, y0 = car.y; int r0 = car.reverts;
          carUpdate(&car, &world, &in, dt);
          propsUpdate(&props, &world, &car, dt);
          spUpdate(&sp, &world, &car, NULL, dt);
          if (car.reverts != r0 && (car.revWhy & 16)) {   // откат «край мира»: это щель?
            float mx = sinf(car.h), mz = cosf(car.h);
            for (float t = 0.05f; t <= 0.6f; t += 0.05f)       // точка, куда шёл подшаг (за кадр не больше ~0.6 м)
              if (crack(x0 + mx * t * 1.2f, z0 + mz * t * 1.2f, mx, mz, y0 + 1.2f)) { cw++; break; }
          }
          if ((car.x - g0->x) * nx + (car.z - g0->z) * nz > 3.f) pass = 1;
        }
        gRuns++; gCrack += cw > 0; gPass += pass;
      }
    }
    printf("glass #%u (%.0f %.0f %.0f) n (%.2f %.2f): runs %d, passed the pane %d, crack walls %d\n", i, g0->x, g0->y, g0->z, nx, nz,
           gRuns, gPass, gCrack);
    runs += gRuns; crackWalls += gCrack; passed += gPass;
  }
  // контроль: настоящий край без стен. Ищем переход «опора -> пустота на 6 м вперёд» без забора и без стены у кромки
  // (иначе держит стена, а не правило края), летим туда на 15 м/с с высоты опора+2.5 и меряем, насколько машина
  // залетела за кромку (конечное положение не годится: без опоры через 1.5 с срабатывает возврат на надёжное место)
  int edgeFound = 0, edgeHeld = 0; float worstPast = 0;
  for (int gz = 4; gz < world.H - 4 && edgeFound < 5; gz += 3) for (int gx = 4; gx < world.W - 4 && edgeFound < 5; gx += 3) {
    float px = world.ox + (gx + .5f) * world.cell, pz = world.oz + (gz + .5f) * world.cell, g0;
    if (!colGround(&world, px, pz, 300.f, -1e6f, &g0, 0)) continue;
    for (int dir = 0; dir < 8 && edgeFound < 5; dir++) {
      float a = dir * 0.7854f, ux = sinf(a), uz = cosf(a), lastG = g0, lastR = 0, edge = -1, g;
      for (float r = 0.5f; r < 30.f; r += .5f) {
        if (colGround(&world, px + ux * r, pz + uz * r, lastG + 3.f, -1e6f, &g, 0)) { if (fabsf(g - lastG) > 1.f) break; lastG = g; lastR = r; continue; }
        edge = r; break;
      }
      if (edge < 0 || edge - lastR > .6f) continue;
      int voidOk = 1;
      for (float r = edge; r < edge + 6.f && voidOk; r += .25f)
        for (float s2 = -2.f; s2 <= 2.f && voidOk; s2 += 1.f)
          if (colGround(&world, px + ux * r - uz * s2, pz + uz * r + ux * s2, 400.f, -1e6f, &g, 0)) voidOk = 0;
      if (!voidOk) continue;
      float ex = px + ux * edge, ez = pz + uz * edge;
      if (colCrossFence(&world, ex - ux * 4, ez - uz * 4, ex + ux * 6, ez + uz * 6, 0, 0)) continue;
      carInit(&car, NULL, &world, ex - ux * 3, lastG + 2.5f, ez - uz * 3, atan2f(ux, uz));
      CarBox cb; carBox(&car, &cb); cb.x = ex; cb.z = ez; if (colProbeCar(&world, &cb)) continue;   // стена у кромки
      car.vel[0] = ux * 15; car.vel[2] = uz * 15; car.vel[1] = 0; car.v = 15;
      float past = -99;
      for (int fr = 0; fr < 50; fr++) { CarInput in = {0}; carUpdate(&car, &world, &in, dt);
        float d = (car.x - ex) * ux + (car.z - ez) * uz; if (d > past) past = d; }
      edgeFound++; if (past > worstPast) worstPast = past;
      printf("edge control %d: (%.0f %.0f) dir %.0f deg, void 6 m wide, flew past the edge by %.1f m\n", edgeFound, ex, ez, a * 57.3f, past);
    }
  }
  edgeHeld = edgeFound && worstPast < 1.5f;
  printf("glass=%d runs=%d started=%d passed=%d crack_walls=%d\n", glass, runs, started, passed, crackWalls);
  check("13 glass ramps found", glass == 13);
  check("every glass ramp has a start on the ground", runs >= 13 * 12);
  check("no crack acts as a world edge (flight over a 0-2 m seam)", crackWalls == 0);
  if (edgeFound) check("a real world edge still stops the car in flight", edgeHeld);
  else printf("SKIP edge control: no void edge found\n");
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
