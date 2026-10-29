// Гейт «поиск пути ИИ-машин»: быстрый planRoads (смежность + куча) даёт те же пути, что прежний перебор, бит в бит.
//   tests/aicar/roadplan.c LEVEL HOMER MSN ; красный контроль: -DROADPLAN_BREAK=1 (нарочно другой порядок равных расстояний) обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "world.h"
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e6 + t.tv_nsec * 1e-3; }
int main(int argc, char **argv) {
  if (bwData(argv[1], argv[2], argv[3])) return 2;
  static BotWorld W; bwNew(&W);
  const Traffic *t = (const Traffic *)bwTraffic(); if (!t || !t->hd) { printf("нет трафика\n"); return 2; }
  mcProbeRoads(t, bwCol());   // как на загрузке: перекрытые дороги и уступы помечены
  int nr = (int)t->hd->nRoad; srand(11);
  int N = 6000, diff = 0, found = 0; double tOld = 0, tNew = 0;
  for (int i = 0; i < N; i++) {
    int r0 = rand() % nr, r1 = rand() % nr; const TrRoad *A = &t->road[r0], *B = &t->road[r1]; if (A->nPt < 1 || B->nPt < 1) continue;
    const TrPt *pa = t->pt + A->firstPt, *pb = t->pt + B->firstPt;
    float x = pa[rand() % A->nPt].x + (rand() % 7 - 3), z = pa[rand() % A->nPt].z + (rand() % 7 - 3), y = pa[0].y;
    float g[3] = {pb[rand() % B->nPt].x + (rand() % 5 - 2), pb[0].y, pb[rand() % B->nPt].z}; float h = (rand() % 628) * .01f;
    int sc = rand() & 1; short av[4]; int nav = rand() % 4; for (int k = 0; k < nav; k++) av[k] = (short)(rand() % nr); mcPlanAvoid(av, nav);
    static float o0[64][3], o1[64][3]; int off0 = 0, off1 = 0;
    mcRoadPlanOld = 1; double t0 = now(); int n0 = mcPlan(t, x, y, z, h, g, sc, o0, 64, &off0); tOld += now() - t0;
    mcRoadPlanOld = 0; t0 = now(); int n1 = mcPlan(t, x, y, z, h, g, sc, o1, 64, &off1); tNew += now() - t0;
    found += n0 > 1;
    if (n0 != n1 || off0 != off1 || memcmp(o0, o1, (size_t)n0 * sizeof o0[0])) { if (diff < 3) printf("  расхождение: пара %d (n %d/%d, offroad %d/%d)\n", i, n0, n1, off0, off1); diff++; }
  }
  mcPlanAvoid(0, 0);
  printf("дорог %d, пар %d (путь по дорогам в %d): расхождений %d; время старый %.1f мкс, новый %.1f мкс на запрос (%.1f×)\n", nr, N, found, diff, tOld / N, tNew / N, tOld / (tNew > 0 ? tNew : 1));
  printf("%s\n", diff ? "FAIL" : "PASS"); return diff != 0;
}
