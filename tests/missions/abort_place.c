// №369: настоящее завершение миссии + вступление, на месте игрока, L1–L7
#include <stdio.h>
#include <math.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc != 4 || bwData(argv[1], argv[2], argv[3])) return 2;
  int bad = 0, count = 0, retried = 0;
  bwNew(&W);
  unsigned n = W.msn.f.nmissions;
  bwFree(&W);
  for (unsigned i = 0; i < n; i++) for (int foot = 0; foot < 2; foot++) {
    bwNew(&W);
    GameMsn *m = &W.msn;
    msn_start_mission(&m->rt, i, 1);
    float x = W.car.x + 13.25f, y = W.car.y + 2.f, z = W.car.z + 17.75f;
    W.car.x = x; W.car.y = y; W.car.z = z; W.car.h = .73f;
    W.homer.x = x + 2; W.homer.y = y; W.homer.z = z + 2;
    if (foot) homerPlace(&W.homer, bwCol(), x + 2, y, z + 2, .73f);
    float hx = W.homer.x, hy = W.homer.y, hz = W.homer.z;
    int wasFoot = gameOnFoot(&W.G);
    m->rt.status = MSN_FAILED;
    unsigned tp = m->teleports;
    gameMsnAbort(m);
    int ok = W.car.x == x && W.car.y == y && W.car.z == z && W.car.h == .73f &&
             W.homer.x == hx && W.homer.y == hy && W.homer.z == hz && gameOnFoot(&W.G) == wasFoot &&
             m->teleports == tp && m->rt.status != MSN_FAILED && !m->keepPlayer;
    printf("ABORT mission=%u foot=%d %s teleports=%u\n", i, foot, ok ? "PASS" : "FAIL", m->teleports - tp);
    bad += !ok; count++;
    // Настоящий Retry всё ещё выполняет команды положения миссии
    msn_start_mission(&m->rt, i, 1);
    W.car.x += 100; W.car.z += 100;
    tp = m->teleports; msn_retry(&m->rt, 1);
    retried += m->teleports > tp;
    bwFree(&W);
  }
  printf("RESULT cases=%d failures=%d retries_repositioned=%d\n", count, bad, retried);
  return bad || !count || !retried;
}
