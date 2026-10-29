#include <stdio.h>
#include <string.h>
#include "msncar.h"

static void parked(McCar *c, const ColWorld *w, float z) {
  memset(c, 0, sizeof *c); strcpy(c->name, "bonus-test");
  carInit(&c->car, 0, w, 0.f, 0.f, z, 0.f);
  c->on = 1; c->mode = MC_PARKED; c->asleep = 1;
}

int main(void) {
  struct { ColHdr h; uint32_t cells[2]; } fixture = {{"COL1", 0.f, 0.f, 1.f, 1, 1, 0, 0, 0, 0, 0, 0}, {0, 0}};
  ColWorld w; if (colInit(&w, &fixture, sizeof fixture)) return 2;
  McEnv e = {0}; MsnCars m;
  e.w = &w; e.noNpcCollide = 1;
  mcInit(&m); m.n = 2; parked(&m.c[0], &w, 0.f); parked(&m.c[1], &w, 1.f);
  carSetSpeed(&m.c[0].car, 5.f); carSetSpeed(&m.c[1].car, -5.f);
  mcUpdate(&m, &e, 1.f / 60.f, 0, 0);
  if (m.c[0].car.carHitV > .01f || m.c[1].car.carHitV > .01f) { puts("FAIL AI↔AI collision was not isolated"); return 1; }
  puts("BONUS AI↔AI collision isolation: PASS");
  colFree(&w);
  return 0;
}
