// №873 (Роб 23.10: «подхожу прямо к проходу с калиткой — дед стоит»): гэг деда gag_s5 (L1, дом Симпсонов, «touch», сфера 6 м) — вход в комнату
// внутри сферы. Зелёный: после шага на 1,5 м внутри сферы гэг стартует. Контроль: стоять на месте входа — не стартует. GAG_ENTRY873_OLD=1 — красный
//   tests/collect/gag_entry873.sh [collect-l1.shr]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "collect.h"
static void *readAll(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0; fseek(f, 0, SEEK_END); long s = ftell(f); rewind(f);
  unsigned char *b = aligned_alloc(16, ((size_t)s + 15) & ~(size_t)15); if (!b || fread(b, 1, (size_t)s, f) != (size_t)s) { fclose(f); free(b); return 0; }
  fclose(f); *n = (size_t)s; return b; }
static int run(Collect *C, int g, float move) {   // -> стартов гэга g
  const CollGag *G = &C->gag[g]; collectNewGame(C);
  for (unsigned k = 0; k < C->ngag; k++) C->st.gagPick[k] = 0;
  float x = G->tx + G->tr * .8f, z = G->tz, y = G->ty;   // вход внутри сферы, у края
  CollPlayer p = {x, y, z, 1, -1, 0}; CollEvent e; int n = 0;
  for (int tries = 0; tries < 200 && !C->st.gagPick[g]; tries++) {   // вход в комнату, пока случайный выбор группы сам не выпадет на деда (как в игре)
    p.room = -1; collectStep(C, &p, 0, 0, 0, 0, 1 / 30.f); p.room = G->room; collectStep(C, &p, 0, 0, 0, 0, 1 / 30.f); }
  if (!C->st.gagPick[g]) { printf("дед не выпал\n"); return -1; }
  while (collectPop(C, &e)) {}
  for (int f = 0; f < 90; f++) { p.x = x - move * (float)f / 90.f; collectStep(C, &p, 0, 0, 0, 0, 1 / 30.f); while (collectPop(C, &e)) if (e.type == CE_GAG_START && e.idx == g) n++; }
  return n;
}
int main(int argc, char **argv) {
  size_t n; void *pak = readAll(argc > 1 ? argv[1] : "build/collect-l1.shr", &n); if (!pak) { printf("нет пакета\n"); return 2; }
  Collect C; memset(&C, 0, sizeof C); if (collectInit(&C, pak, (unsigned)n)) { printf("collectInit\n"); return 2; }
  int g = -1; for (unsigned k = 0; k < C.ngag; k++) if (!strcmp(C.gag[k].name, "gag_s5")) g = (int)k;
  if (g < 0) { printf("нет gag_s5\n"); return 2; }
  int a = run(&C, g, 1.5f), b = run(&C, g, 0.f);
  printf("gag_s5 (r %.1f м): шаг 1,5 м внутри сферы — стартов %d; стоит на входе — %d\n", C.gag[g].tr, a, b);
  int ok = a >= 1 && b == 0; printf("RESULT: %s\n", ok ? "OK" : "FAIL"); return ok ? 0 : 1;
}
